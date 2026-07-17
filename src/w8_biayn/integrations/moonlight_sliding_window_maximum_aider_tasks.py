"""Materialize newly-authored local sliding-window-maximum Aider tasks."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/sliding-window-maximum")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SLIDING_WINDOW_MAXIMUM_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str; class_name: str; ingest: str; report: str; timed: bool; latest_tie: bool; threshold: bool; blurb: str


_ROWS = (
    ("swmax-stock-peaks", "StockPeakTracker", "record_trade", "highest_recent_price", False, False, False, "Report the earliest highest price in a bounded recent trade window."),
    ("swmax-temperature-alerts", "TemperatureAlertMonitor", "record_temperature", "hottest_recent_reading", False, True, True, "Track recent temperatures and report whether the current maximum crosses an alert threshold."),
    ("swmax-network-latency", "NetworkLatencyWatch", "record_probe", "worst_recent_latency", False, False, False, "Return the earliest probe with the worst latency in the latest probe-count window."),
    ("swmax-cpu-bursts", "CpuBurstSampler", "sample_load", "peak_recent_load", False, True, True, "Identify the latest equal peak CPU load and flag burst thresholds."),
    ("swmax-power-demand", "PowerDemandMeter", "record_interval", "maximum_recent_demand", False, False, True, "Measure the maximum demand over a fixed number of meter intervals."),
    ("swmax-heart-rate", "HeartRateMonitor", "record_beat", "highest_recent_beat", False, False, True, "Report the earliest maximum beat and its sample index in a recent beat window."),
    ("swmax-wind-gusts", "WindGustLog", "record_gust", "strongest_active_gust", True, True, True, "Track the strongest gust in an inclusive rolling time duration."),
    ("swmax-video-bitrate", "VideoBitrateGuard", "record_segment", "highest_available_bitrate", False, True, False, "Record valid segment bitrates and reject invalid segment measurements without changing state."),
    ("swmax-warehouse-throughput", "WarehouseThroughputBoard", "complete_interval", "peak_recent_picks", False, False, False, "Calculate the highest completed-pick count in recent work intervals."),
    ("swmax-game-score-streak", "GameScoreStreak", "finish_turn", "best_recent_turn", False, True, False, "Return the latest equal high score from the last configured turns."),
    ("swmax-web-traffic", "WebTrafficWindow", "observe_second", "busiest_recent_second", True, False, True, "Track the maximum requests-per-second across a rolling observation duration."),
    ("swmax-log-severity", "LogSeverityWindow", "append_event", "highest_recent_severity", False, True, True, "Maintain maximum valid severity among the newest event-count window."),
    ("swmax-machine-vibration", "MachineVibrationMonitor", "sample_amplitude", "maximum_recent_amplitude", False, False, True, "Return the highest recent non-negative vibration amplitude."),
    ("swmax-route-speed", "RouteSpeedWindow", "record_distance_sample", "fastest_recent_sample", False, True, False, "Identify the latest equal maximum speed in recent distance samples."),
    ("swmax-battery-drain", "BatteryDrainTracker", "record_measurement", "largest_recent_drain", False, False, True, "Track the largest recent non-negative drain rate and an over-budget signal."),
    ("swmax-auction-bids", "AuctionBidWindow", "place_bid", "highest_recent_bid", False, True, False, "Report the latest equal highest bid in a bounded recent-bid window."),
    ("swmax-support-load", "SupportLoadCalendar", "close_day", "highest_recent_open_count", False, False, True, "Calculate the peak daily open-ticket count over recent closed days."),
    ("swmax-production-defects", "ProductionDefectWindow", "inspect_batch", "worst_recent_batch", False, True, True, "Find the latest equal maximum defect count in the newest manufacturing batches."),
    ("swmax-rainfall", "RainfallIntensityWindow", "record_scan", "peak_active_intensity", True, False, True, "Report peak rainfall intensity in an inclusive rolling time horizon."),
    ("swmax-delivery-delay", "DeliveryDelayWatch", "scan_delivery", "worst_recent_delay", False, True, True, "Track the latest equal worst delay among the most recent delivery scans."),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text() != content and not force: raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)


def _header(s: TaskSpec) -> str:
    threshold = ", int alert_threshold" if s.threshold else ""
    ingest = f"bool {s.ingest}(long long timestamp, int value);" if s.timed else f"bool {s.ingest}(int value);"
    alert = "bool alert_active() const;" if s.threshold else ""
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <cstddef>
#include <deque>
#include <optional>
namespace curriculum {{
struct PeakSample {{ int value; std::size_t sample_index; long long timestamp; }};
class {s.class_name} {{ public:
  explicit {s.class_name}(std::size_t window{threshold});
  {ingest} std::optional<PeakSample> {s.report}() const; {alert}
  std::size_t accepted_samples() const; void reset();
private:
  struct Sample {{ long long timestamp; int value; std::size_t index; }};
  bool accept(long long timestamp, int value); void expire(long long now);
  std::size_t window_; std::size_t accepted_ = 0; long long last_timestamp_ = -1; int threshold_ = 0;
  std::deque<Sample> active_; std::deque<Sample> candidates_;
}};
}}  // namespace curriculum
#endif
'''


def _reference(s: TaskSpec) -> str:
    ctor = ", int alert_threshold" if s.threshold else ""
    init = ", threshold_(alert_threshold)" if s.threshold else ""
    comparison = "<=" if s.latest_tie else "<"
    ingest = f"bool {s.class_name}::{s.ingest}(long long timestamp, int value) {{ return accept(timestamp, value); }}" if s.timed else f"bool {s.class_name}::{s.ingest}(int value) {{ return accept(static_cast<long long>(accepted_), value); }}"
    expiry = "while (!active_.empty() && active_.front().timestamp < now-static_cast<long long>(window_)) { if (!candidates_.empty() && candidates_.front().index==active_.front().index) candidates_.pop_front(); active_.pop_front(); }" if s.timed else "while (active_.size()>window_) { if (!candidates_.empty() && candidates_.front().index==active_.front().index) candidates_.pop_front(); active_.pop_front(); }"
    alert = f"bool {s.class_name}::alert_active() const {{ const auto peak={s.report}(); return peak && peak->value>=threshold_; }}" if s.threshold else ""
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t window{ctor}) : window_(window){init} {{}}
void {s.class_name}::expire(long long now) {{ (void)now; {expiry} }}
bool {s.class_name}::accept(long long timestamp, int value) {{
  if (window_==0U || value<0 || timestamp<last_timestamp_) return false;
  last_timestamp_=timestamp; const Sample sample{{timestamp,value,accepted_++}}; active_.push_back(sample);
  while (!candidates_.empty() && candidates_.back().value {comparison} sample.value) candidates_.pop_back();
  candidates_.push_back(sample); expire(timestamp); return true;
}}
{ingest}
std::optional<PeakSample> {s.class_name}::{s.report}() const {{ if(candidates_.empty()) return std::nullopt; const auto& p=candidates_.front(); return PeakSample{{p.value,p.index,p.timestamp}}; }}
{alert}
std::size_t {s.class_name}::accepted_samples() const {{ return accepted_; }}
void {s.class_name}::reset() {{ accepted_=0; last_timestamp_=-1; active_.clear(); candidates_.clear(); }}
}}  // namespace curriculum
'''


def _starter(s: TaskSpec) -> str:
    ctor = ", int" if s.threshold else ""
    ingest = f"bool {s.class_name}::{s.ingest}(long long, int) {{ return false; }}" if s.timed else f"bool {s.class_name}::{s.ingest}(int) {{ return false; }}"
    alert = f"bool {s.class_name}::alert_active() const {{ return false; }}" if s.threshold else ""
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t{ctor}) : window_(0) {{}}
bool {s.class_name}::accept(long long, int) {{ return false; }} void {s.class_name}::expire(long long) {{}}
{ingest} std::optional<PeakSample> {s.class_name}::{s.report}() const {{ return std::nullopt; }}
{alert} std::size_t {s.class_name}::accepted_samples() const {{ return 0; }} void {s.class_name}::reset() {{}}
}}  // namespace curriculum
'''


def _call(s: TaskSpec, obj: str, timestamp: str, value: str) -> str:
    return f"{obj}.{s.ingest}({timestamp}, {value})" if s.timed else f"{obj}.{s.ingest}({value})"


def _test(s: TaskSpec, hidden: bool) -> str:
    args = "3, 50" if s.threshold else "3"
    calls = " ".join(f"check({_call(s, 'window', str(i), str(v))});" for i, v in enumerate((10, 50, 50, 20)))
    index = "2U" if s.latest_tie else "1U"
    alert = "check(window.alert_active());" if s.threshold else ""
    trace = ""
    if hidden:
        eviction = "while(!oracle.empty() && step>3 && oracle.front().second < static_cast<std::size_t>(step-3)) oracle.pop_front();" if s.timed else "while(oracle.size()>3U) oracle.pop_front();"
        trace = f'''\n  curriculum::{s.class_name} trace({args}); std::deque<std::pair<int,std::size_t>> oracle;
  for(int step=0;step<1500;++step) {{ int value=(step*37)%101; check({_call(s,'trace','step','value')}); oracle.push_back({{value,static_cast<std::size_t>(step)}}); {eviction} int best=-1; std::size_t best_index=0; for(const auto& item:oracle) if(item.first>best {'|| item.first==best' if s.latest_tie else ''}) {{ best=item.first; best_index=item.second; }} const auto got=trace.{s.report}(); check(got && got->value==best && got->sample_index==best_index); }}'''
    return f'''#include "task.h"
#include <deque>
int main() {{ int failures=0; const auto check=[&](bool ok){{if(!ok)++failures;}};
  curriculum::{s.class_name} zero(0{', 50' if s.threshold else ''}); check(!{_call(s,'zero','0','1')});
  curriculum::{s.class_name} window({args}); {calls} const auto peak=window.{s.report}(); check(peak && peak->value==50 && peak->sample_index=={index}); {alert}
  check(!{_call(s,'window','9','-1')}); {'check(!'+_call(s,'window','1','60')+');' if s.timed else ''} window.reset(); check(!window.{s.report}()); check(window.accepted_samples()==0U);{trace}
  return failures==0?0:1;
}}
'''


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(sliding_window_maximum_curriculum LANGUAGES CXX)
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
    roots = []
    for s in TASKS:
        root = out / s.task_id; header = _header(s)
        config = {"authors":["w8-biayn"],"blurb":s.blurb,"files":{"solution":["task.h","task.cpp"],"test":["task_visible_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
        provenance = {"curriculum_document":CURRICULUM,"curriculum_task_id":s.task_id,"origin":"newly-authored in-repository diagnostic task","status":"local task artifact; not admitted SFT data","version":1,"benchmark_separation":"Not derived from an official Aider Polyglot task; domain API, invalid-input behavior, tie policy, and time/count window semantics are independently authored."}
        mode = "inclusive timestamp-duration expiry and stale-timestamp rejection" if s.timed else "event-count expiry"
        tie = "latest" if s.latest_tie else "earliest"
        files = {".docs/introduction.md":f"# {s.class_name}\n\nA newly authored local monotonic-deque diagnostic task.\n", ".docs/instructions.md":f"# Instructions\n\nImplement `{s.class_name}`. {s.blurb} The configured window uses {mode}. Negative measurements are rejected without state mutation. Equal maxima select the {tie} sample. A zero window rejects every measurement. `reset()` clears state and indices.\n", ".meta/config.json":json.dumps(config,indent=2,sort_keys=True)+"\n", ".meta/provenance.json":json.dumps(provenance,indent=2,sort_keys=True)+"\n", ".meta/tests.toml":"[visible]\ndescription = \"domain API, zero window, rejection, tie policy, expiry, reset, and report behavior\"\n\n[hidden]\ndescription = \"boundary windows, increasing/decreasing/equal streams, immediate peak expiry, stale timestamps, long adversarial traces, and brute-force oracle comparison\"\n", "task.h":header, "task.cpp":_starter(s), ".meta/example.h":header, ".meta/example.cpp":_reference(s), "task_visible_test.cpp":_test(s,False), ".meta/task_hidden_test.cpp":_test(s,True), "CMakeLists.txt":_cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for s in TASKS:
        with tempfile.TemporaryDirectory(prefix="sliding-window-maximum-") as temporary:
            copied = Path(temporary) / s.task_id; shutil.copytree(out / s.task_id, copied)
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake","-S",str(copied),"-B",str(build_dir),f"-DTASK_SOURCE={copied / '.meta/example.cpp'}",*flags],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                subprocess.run(["cmake","--build",str(build_dir),"--parallel","2"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                subprocess.run(["ctest","--test-dir",str(build_dir),"--output-on-failure"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format sliding-window-maximum curriculum tasks.")
    parser.add_argument("--out",type=Path,default=DEFAULT_OUT); parser.add_argument("--force",action="store_true"); parser.add_argument("--verify",action="store_true")
    args = parser.parse_args(argv); roots = build(args.out,args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} sliding-window-maximum curriculum tasks under {args.out}"); return 0


if __name__ == "__main__": raise SystemExit(main())
