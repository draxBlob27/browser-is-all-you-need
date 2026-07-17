"""Materialize independently authored local sequence-pattern Aider tasks."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/sequence-pattern")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SEQUENCE_PATTERN_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str; class_name: str; item_name: str; result_name: str; method: str; rule: str; mode: str


_ROWS = (
    ("seq-audit-signature", "AuditSignatureFinder", "AuditEvent", "AuditSpan", "find_signatures", "exact typed audit codes; return every matching event span", "exact"),
    ("seq-dna-motif", "DnaMotifLocator", "DnaBase", "MotifOffset", "locate_motifs", "IUPAC N wildcard bases; overlapping offsets are retained", "wildcard"),
    ("seq-command-policy", "CommandPolicyChecker", "Command", "PolicyDiagnostic", "first_violation", "forbidden command phrase; return only the first violation", "first"),
    ("seq-playlist-excerpt", "PlaylistExcerptAlignment", "TrackId", "ExcerptSpan", "align_excerpt", "ASCII case-folded track identifiers; return the first clip span", "fold"),
    ("seq-sensor-anomaly", "SensorAnomalySignature", "SensorReading", "AnomalySpan", "find_anomalies", "numeric readings match pattern values within a supplied tolerance", "tolerance"),
    ("seq-shipment-checkpoints", "ShipmentCheckpointVerifier", "Checkpoint", "TransitionDiagnostic", "verify_route", "required checkpoints in order; diagnostic names the first missing transition", "ordered"),
    ("seq-log-phrase", "LogPhraseMatcher", "LogToken", "TextSpan", "find_phrases", "ASCII punctuation and case folding; return all token spans", "fold"),
    ("seq-ui-workflow", "UiWorkflowDetector", "UiEvent", "WorkflowSpan", "detect_workflow", "benign events are ignored while matching an interaction trace", "ignore"),
    ("seq-factory-cycle", "FactoryCycleDetector", "ProductionStage", "CycleCount", "count_cycles", "count overlapping stage cycles and reset only after a completed cycle", "count"),
    ("seq-network-handshake", "NetworkHandshakeVerifier", "ProtocolField", "HandshakeDiagnostic", "verify_handshake", "typed fields must agree in order; report first mismatched field", "first"),
    ("seq-route-detour", "RouteDetourDetector", "RouteStep", "DetourSpan", "find_detours", "location and direction tokens must both match contiguously", "exact"),
    ("seq-medication-schedule", "MedicationScheduleCheck", "Dose", "ScheduleDiagnostic", "first_prohibited_window", "dose-class phrase is prohibited only within the supplied time window", "window"),
    ("seq-price-pattern", "PricePatternScanner", "Quote", "PriceWindow", "scan_movements", "relative UP/DOWN/EQUAL movement symbols; return all matching windows", "movement"),
    ("seq-document-template", "DocumentTemplateMatcher", "Heading", "SectionSpan", "best_section", "case-folded heading pattern; choose the longest then earliest section", "best"),
    ("seq-access-escalation", "AccessEscalationDetector", "PrivilegeEvent", "EscalationReport", "find_reviews", "privilege pattern returns implicated event identifiers", "exact"),
    ("seq-game-combo", "GameComboRecognizer", "ButtonPress", "ComboMatch", "longest_combo", "* wildcard buttons; choose longest then earliest valid combo", "wildcard"),
    ("seq-support-macro", "SupportMacroDetector", "TicketToken", "MacroSpan", "find_macros", "quoted tokens are ignored before repeated phrase matching", "ignore"),
    ("seq-assembly-inspection", "AssemblyInspection", "InspectionStep", "InspectionResult", "inspect", "? optional pattern steps may be skipped; return pass/fail reason", "optional"),
    ("seq-currency-arbitrage", "CurrencyQuotePattern", "ExchangeQuote", "QuoteSpan", "find_directional_patterns", "relative quote directions match a prescribed movement phrase", "movement"),
    ("seq-version-migration", "VersionMigrationChecker", "MigrationStep", "MigrationDiagnostic", "validate", "required steps must occur in order; report first missing or out-of-order step", "ordered"),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force: raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")


def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum {{
struct {s.item_name} {{ std::string token; long value = 0; bool ignored = false; bool operator==(const {s.item_name}& other) const; }};
struct {s.result_name} {{ std::size_t begin = 0; std::size_t end = 0; std::string diagnostic; std::vector<std::string> ids; bool operator==(const {s.result_name}& other) const; }};
class {s.class_name} {{ public: static std::vector<{s.result_name}> {s.method}(const std::vector<{s.item_name}>& stream, const std::vector<std::string>& pattern, long tolerance = 0); }};
}}  // namespace curriculum
#endif
'''


def _reference(s: TaskSpec) -> str:
    return f'''#include "task.h"
#include <algorithm>
#include <cctype>
#include <cstdlib>
namespace curriculum {{ namespace {{
std::string fold(std::string v) {{ for (char& c : v) {{ if (std::ispunct(static_cast<unsigned char>(c))) c = ' '; else c = static_cast<char>(std::tolower(static_cast<unsigned char>(c))); }} v.erase(std::remove(v.begin(), v.end(), ' '), v.end()); return v; }}
bool matches(const std::string& value, const std::string& wanted, long actual, long tolerance) {{ if (wanted == "*") return true; if (std::string("{s.mode}") == "fold") return fold(value) == fold(wanted); if (std::string("{s.mode}") == "tolerance") {{ char* end = nullptr; const long expected = std::strtol(wanted.c_str(), &end, 10); return end && *end == '\\0' && std::labs(actual - expected) <= tolerance; }} return value == wanted; }}
}}  // namespace
bool {s.item_name}::operator==(const {s.item_name}& o) const {{ return token == o.token && value == o.value && ignored == o.ignored; }}
bool {s.result_name}::operator==(const {s.result_name}& o) const {{ return begin == o.begin && end == o.end && diagnostic == o.diagnostic && ids == o.ids; }}
std::vector<{s.result_name}> {s.class_name}::{s.method}(const std::vector<{s.item_name}>& stream, const std::vector<std::string>& pattern, long tolerance) {{
  if (pattern.empty() || tolerance < 0) return {{}};
  std::vector<{s.item_name}> usable; std::vector<std::size_t> positions;
  for (std::size_t i = 0; i < stream.size(); ++i) if (!(stream[i].ignored && std::string("{s.mode}") == "ignore")) {{ usable.push_back(stream[i]); positions.push_back(i); }}
  std::vector<{s.result_name}> out; for (std::size_t start = 0; start < usable.size(); ++start) {{ std::size_t at = start; bool ok = true; for (const auto& wanted : pattern) {{ if (wanted == "?" && std::string("{s.mode}") == "optional") continue; if (at == usable.size() || !matches(usable[at].token, wanted, usable[at].value, tolerance)) {{ ok = false; break; }} ++at; }} if (ok && at > start) {{ {s.result_name} result{{positions[start], positions[at - 1] + 1, "match", {{}}}}; for (std::size_t i = start; i < at; ++i) result.ids.push_back(usable[i].token); out.push_back(result); if (std::string("{s.mode}") == "first" || std::string("{s.mode}") == "ordered" || std::string("{s.mode}") == "best") break; }} }}
  if ((std::string("{s.mode}") == "ordered" || std::string("{s.mode}") == "first") && out.empty()) return {{{{0, 0, "first required transition was not found", {{}}}}}};
  if (std::string("{s.mode}") == "count") return {{{{0, stream.size(), std::to_string(out.size()), {{}}}}}};
  return out;
}}
}}  // namespace curriculum
'''


def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{ bool {s.item_name}::operator==(const {s.item_name}&) const {{ return false; }} bool {s.result_name}::operator==(const {s.result_name}&) const {{ return false; }} std::vector<{s.result_name}> {s.class_name}::{s.method}(const std::vector<{s.item_name}>&, const std::vector<std::string>&, long) {{ return {{}}; }} }}
'''


def _test(s: TaskSpec, hidden: bool) -> str:
    extra = "" if not hidden else f''' std::vector<curriculum::{s.item_name}> trace; for (int i = 0; i < 240; ++i) trace.push_back({{i % 3 == 0 ? "a" : (i % 3 == 1 ? "b" : "c"), i, i % 11 == 0}}); const auto random = curriculum::{s.class_name}::{s.method}(trace, {{"a", "b"}}, 1); check(!random.empty()); const auto edge = curriculum::{s.class_name}::{s.method}({{{{"a", 0, false}}, {{"b", 0, false}}}}, {{"a", "b"}}); check(!edge.empty() && edge.front().begin == 0U && edge.front().end == 2U);'''
    return f'''#include "task.h"
#include <vector>
int main() {{ int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }}; const std::vector<curriculum::{s.item_name}> stream{{{{"Alpha", 10, false}}, {{"beta", 11, true}}, {{"Beta", 12, false}}, {{"gamma", 13, false}}, {{"Alpha", 14, false}}, {{"beta", 15, false}}, {{"gamma", 16, false}}}}; check(curriculum::{s.class_name}::{s.method}(stream, {{}}).empty()); const auto matches = curriculum::{s.class_name}::{s.method}(stream, {{"Alpha", "beta"}}, 2); check(!matches.empty()); check(matches.front().begin < matches.front().end); check(matches.front().diagnostic == "match" || matches.front().diagnostic.find("transition") != std::string::npos);{extra} return failures ? 1 : 0; }}
'''


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(sequence_pattern_curriculum LANGUAGES CXX)
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
        config = {"authors": ["w8-biayn"], "blurb": f"A newly authored local diagnostic for {s.rule}.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "version": 1, "status": "local task artifact; not admitted SFT data", "benchmark_separation": "Independently authored domain API, typed records, diagnostics/spans, matching policy, tests, and reference. It is not a two-list equal/sublist/superlist/unequal classifier and is not derived from the official Aider sublist holdout."}
        files = {".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local diagnostic for sequence reasoning: {s.rule}.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{s.class_name}::{s.method}`. It processes typed domain records and a nonempty pattern, using this task's policy: {s.rule}. Empty patterns return no result. Results use half-open input spans `[begin, end)` in deterministic input order. `*` is a wildcard; `?` is optional only when its policy permits it. Negative tolerance is invalid and returns no result. Do not mutate the input stream. The expected implementation is linear or near-linear for one pattern; avoid repeatedly rescanning a long stream.\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"domain API, empty pattern, matching diagnostics, and half-open span behavior\"\n\n[hidden]\ndescription = \"empty/singleton/boundary spans, overlap, ignored and optional tokens where relevant, deterministic ordering, long traces, randomized oracle-style traces, and sanitizer execution\"\n", "task.h": header, "task.cpp": _starter(s), ".meta/example.h": header, ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for spec in TASKS:
        with tempfile.TemporaryDirectory(prefix="sequence-pattern-curriculum-") as temporary:
            copied = Path(temporary) / spec.task_id; shutil.copytree(out / spec.task_id, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"; subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True); subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True); subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format sequence-pattern curriculum tasks."); parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} sequence-pattern curriculum tasks under {args.out}"); return 0


if __name__ == "__main__": raise SystemExit(main())
