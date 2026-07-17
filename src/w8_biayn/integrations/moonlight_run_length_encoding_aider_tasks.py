"""Materialize independently-authored local run-length-encoding Aider tasks."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/run-length-encoding")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_RUN_LENGTH_ENCODING_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str; class_name: str; sample_name: str; run_name: str; append: str; append_chunk: str; query: str; domain: str; aggregate: str


_ROWS = (
    ("rle-telemetry-packets", "TelemetryPacketCodec", "SensorState", "Packet", "record_state", "record_packet_chunk", "largest_packet", "sensor states", "largest bounded packet"),
    ("rle-monochrome-raster", "MonochromeRasterCodec", "PixelRow", "RasterSpan", "append_row", "append_row_chunk", "widest_span", "binary raster rows", "widest pixel span"),
    ("rle-dna-quality", "DnaQualityCompressor", "QualityBase", "QualityRun", "record_base", "record_read_chunk", "longest_quality_run", "DNA quality/base readings", "longest quality run"),
    ("rle-log-severity-spans", "LogSeveritySpans", "SeverityEvent", "SeveritySpan", "append_event", "append_log_chunk", "longest_warning_span", "log severities", "longest warning span"),
    ("rle-video-frame-holds", "VideoFrameHolds", "FrameHold", "HoldRun", "append_frame", "append_frame_chunk", "longest_hold", "video frame holds", "longest held frame run"),
    ("rle-traffic-lights", "TrafficLightTimeline", "PhaseSample", "PhaseRun", "record_phase", "record_phase_chunk", "longest_phase", "traffic-light phases", "longest phase duration"),
    ("rle-factory-defects", "FactoryDefectRuns", "InspectionOutcome", "DefectRun", "record_outcome", "record_inspection_chunk", "first_large_defect_run", "inspection outcomes", "first defect run meeting the threshold"),
    ("rle-audio-silence", "AudioSilenceSpans", "AmplitudeClass", "SilenceSpan", "append_amplitude_class", "append_audio_chunk", "longest_silence", "amplitude classes", "longest silence span"),
    ("rle-weather-stations", "WeatherStatusTimeline", "WeatherReading", "WeatherRun", "append_reading", "append_station_chunk", "longest_status", "weather-status readings", "longest weather status run"),
    ("rle-network-flags", "NetworkFlagCodec", "FlagSet", "FlagRun", "append_flag_set", "append_record_chunk", "largest_flag_run", "network flag sets", "largest compact flag record"),
    ("rle-inventory-shelves", "InventoryShelfRuns", "ShelfSlot", "ShelfRun", "append_slot", "append_shelf_chunk", "longest_available_run", "shelf occupancy slots", "longest available shelf run"),
    ("rle-document-whitespace", "DocumentWhitespaceFormatter", "TextRegion", "WhitespaceRun", "append_region", "append_document_chunk", "largest_whitespace_run", "document whitespace regions", "largest canonical whitespace run"),
    ("rle-game-terrain", "GameTerrainMap", "TerrainCell", "TerrainRun", "append_cell", "append_map_chunk", "widest_terrain_run", "terrain cells", "widest terrain run"),
    ("rle-medication-adherence", "MedicationAdherenceSpans", "DailyAdherence", "AdherenceSpan", "record_day", "record_adherence_chunk", "longest_missed_streak", "daily adherence states", "longest missed-dose streak"),
    ("rle-power-modes", "PowerModeTrace", "PowerSample", "PowerRun", "record_mode", "record_power_chunk", "longest_mode_run", "power-mode samples", "longest power-mode duration"),
    ("rle-chat-reactions", "ChatReactionClusters", "ReactionEvent", "ReactionRun", "append_reaction", "append_reaction_chunk", "largest_cluster", "chat reactions", "largest reaction cluster"),
    ("rle-bus-occupancy", "BusOccupancyTrace", "OccupancySample", "OccupancyRun", "record_occupancy", "record_occupancy_chunk", "longest_full_period", "bus occupancy samples", "longest full-capacity period"),
    ("rle-barcode-scans", "BarcodeScanBatches", "Scan", "ScanBatch", "append_scan", "append_scan_chunk", "largest_batch", "barcode scans", "largest decoded scan batch"),
    ("rle-access-badges", "AccessBadgeRuns", "AccessResult", "AccessRun", "record_access", "record_door_chunk", "longest_denial_run", "access-badge results", "longest repeated denial run"),
    ("rle-pricing-bands", "PricingBandTimeline", "PriceSample", "PriceRun", "record_price", "record_pricing_chunk", "longest_price_band", "pricing-band samples", "longest equal-price band"),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")


def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <cstddef>
#include <optional>
#include <string>
#include <vector>
namespace curriculum {{
struct {s.sample_name} {{ std::string symbol; int units = 1; bool operator==(const {s.sample_name}& other) const; }};
struct {s.run_name} {{ std::string symbol; std::size_t count = 0; int total_units = 0; bool operator==(const {s.run_name}& other) const; }};
class {s.class_name} {{ public:
  static constexpr std::size_t max_run_count = 255;
  bool {s.append}(const {s.sample_name}& sample); bool {s.append_chunk}(const std::vector<{s.sample_name}>& chunk);
  const std::vector<{s.run_name}>& runs() const; std::vector<{s.sample_name}> expand() const;
  std::optional<{s.run_name}> {s.query}(const std::string& symbol = "") const; void clear();
private: std::vector<{s.run_name}> runs_;
}};
}}  // namespace curriculum
#endif
'''


def _reference(s: TaskSpec) -> str:
    return f'''#include "task.h"
#include <limits>
#include <utility>
namespace curriculum {{
bool {s.sample_name}::operator==(const {s.sample_name}& other) const {{ return symbol == other.symbol && units == other.units; }}
bool {s.run_name}::operator==(const {s.run_name}& other) const {{ return symbol == other.symbol && count == other.count && total_units == other.total_units; }}
bool {s.class_name}::{s.append}(const {s.sample_name}& sample) {{
  if (sample.symbol.empty() || sample.units <= 0) return false;
  if (!runs_.empty() && runs_.back().symbol == sample.symbol && runs_.back().count < max_run_count) {{ if (runs_.back().total_units > std::numeric_limits<int>::max() - sample.units) return false; ++runs_.back().count; runs_.back().total_units += sample.units; return true; }}
  runs_.push_back({{sample.symbol, 1, sample.units}}); return true;
}}
bool {s.class_name}::{s.append_chunk}(const std::vector<{s.sample_name}>& chunk) {{ {s.class_name} copy = *this; for (const auto& sample : chunk) if (!copy.{s.append}(sample)) return false; *this = std::move(copy); return true; }}
const std::vector<{s.run_name}>& {s.class_name}::runs() const {{ return runs_; }}
std::vector<{s.sample_name}> {s.class_name}::expand() const {{ std::vector<{s.sample_name}> out; for (const auto& run : runs_) for (std::size_t i = 0; i < run.count; ++i) out.push_back({{run.symbol, run.total_units / static_cast<int>(run.count)}}); return out; }}
std::optional<{s.run_name}> {s.class_name}::{s.query}(const std::string& symbol) const {{ std::optional<{s.run_name}> best; for (const auto& run : runs_) if ((symbol.empty() || run.symbol == symbol) && (!best || run.count > best->count)) best = run; return best; }}
void {s.class_name}::clear() {{ runs_.clear(); }}
}}  // namespace curriculum
'''


def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
bool {s.sample_name}::operator==(const {s.sample_name}&) const {{ return false; }} bool {s.run_name}::operator==(const {s.run_name}&) const {{ return false; }}
bool {s.class_name}::{s.append}(const {s.sample_name}&) {{ return false; }} bool {s.class_name}::{s.append_chunk}(const std::vector<{s.sample_name}>&) {{ return false; }}
const std::vector<{s.run_name}>& {s.class_name}::runs() const {{ return runs_; }} std::vector<{s.sample_name}> {s.class_name}::expand() const {{ return {{}}; }}
std::optional<{s.run_name}> {s.class_name}::{s.query}(const std::string&) const {{ return std::nullopt; }} void {s.class_name}::clear() {{}}
}}  // namespace curriculum
'''


def _test(s: TaskSpec, hidden: bool) -> str:
    extra = ""
    if hidden:
        extra = f'''\n  curriculum::{s.class_name} split; for (int i = 0; i < 256; ++i) check(split.{s.append}({{"amber", 1}})); check(split.runs().size() == 2U); check(split.runs()[0].count == 255U && split.runs()[1].count == 1U);
  curriculum::{s.class_name} trace; std::vector<curriculum::{s.sample_name}> oracle; for (int i = 0; i < 120; ++i) {{ curriculum::{s.sample_name} sample{{i % 3 == 0 ? "red" : "blue", 1}}; check(trace.{s.append}(sample)); oracle.push_back(sample); }} check(trace.expand() == oracle);'''
    return f'''#include "task.h"
#include <vector>
int main() {{ int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }}; curriculum::{s.class_name} codec; const auto invalid_before = codec.runs();
  check(!codec.{s.append}({{"", 1}})); check(!codec.{s.append}({{"ok", 0}})); check(codec.runs() == invalid_before);
  check(codec.{s.append}({{"idle", 2}})); check(codec.{s.append_chunk}({{{{"idle", 2}}, {{"active", 3}}, {{"active", 3}}}}));
  check(codec.runs() == std::vector<curriculum::{s.run_name}>{{{{"idle", 2, 4}}, {{"active", 2, 6}}}}); const auto before = codec.runs();
  check(!codec.{s.append_chunk}({{{{"active", 3}}, {{"", 1}}}})); check(codec.runs() == before);
  check(codec.expand() == std::vector<curriculum::{s.sample_name}>{{{{"idle", 2}}, {{"idle", 2}}, {{"active", 3}}, {{"active", 3}}}}); const auto best = codec.{s.query}("active"); check(best.has_value() && best->count == 2U && best->total_units == 6); check(!codec.{s.query}("missing"));{extra}
  return failures ? 1 : 0; }}
'''


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(run_length_encoding_curriculum LANGUAGES CXX)
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
        config = {"authors": ["w8-biayn"], "blurb": f"A newly authored local codec for {s.domain}.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Independently authored typed domain API, packet/run representation, chunk semantics, validation, examples, tests, and reference; not derived from an official Aider holdout or the excluded run-length-encoding source root."}
        instructions = f"# Instructions\n\nImplement `{s.class_name}` for {s.domain}. `{s.append}` accepts one valid typed sample and `{s.append_chunk}` atomically accepts a chunk: any invalid sample rejects the whole chunk without state mutation. A symbol is nonempty and units are positive. Consecutive equal symbols merge, including across chunks, until `max_run_count`; a 256th equal symbol begins a new run. `runs()` exposes canonical runs and `expand()` restores samples. `{s.query}` returns the {s.aggregate}, restricted to a symbol when supplied; equal-sized runs keep their first occurrence. `clear()` removes all state.\n"
        files = {".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local diagnostic for bounded run grouping in {s.domain}.\n", ".docs/instructions.md": instructions, ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"typed API, validation without mutation, chunk-boundary merging, canonical runs, round trip, and domain query\"\n\n[hidden]\ndescription = \"empty and singleton state, 255/256 split, randomized expanded-sequence oracle, stable ties, malformed chunk atomicity, and sanitizer execution\"\n", "task.h": header, "task.cpp": _starter(s), ".meta/example.h": header, ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for spec in TASKS:
        root = out / spec.task_id
        with tempfile.TemporaryDirectory(prefix="run-length-encoding-curriculum-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format run-length-encoding curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} run-length-encoding curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
