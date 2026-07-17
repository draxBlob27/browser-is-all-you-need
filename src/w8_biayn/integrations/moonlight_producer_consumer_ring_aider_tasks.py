"""Materialize the newly-authored producer-consumer-ring curriculum roots.

These task directories are local diagnostic artifacts only. They deliberately
use domain-specific APIs and are not a substitute for primary SFT admission.
"""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/producer-consumer-ring")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_PRODUCER_CONSUMER_RING_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    publish: str
    consume: str
    close: str
    noun: str
    policy: str
    cardinality: str


_ROWS = (
    ("pcr-audio-capture", "AudioCaptureRing", "capture_frame", "take_playback_frame", "finish_capture", "audio frames", "block", "single-producer/single-consumer"),
    ("pcr-camera-frames", "CameraFrameRing", "capture_frame", "take_render_frame", "close_camera", "camera frames", "drop_oldest", "single-producer/single-consumer"),
    ("pcr-telemetry-uplink", "TelemetryUplinkRing", "submit_reading", "take_uplink_reading", "close_uplink", "telemetry readings", "block", "multi-producer/single-consumer"),
    ("pcr-network-receiver", "NetworkReceiverRing", "receive_packet", "take_packet", "close_receiver", "network packets", "block", "multi-producer/multi-consumer"),
    ("pcr-log-ingest", "LogIngestRing", "append_record", "take_log_record", "close_ingest", "log records", "reject", "multi-producer/single-consumer"),
    ("pcr-keyboard-events", "KeyboardEventRing", "emit_event", "take_ui_event", "close_input", "keyboard events", "reject", "single-producer/single-consumer"),
    ("pcr-can-bus", "CanBusRing", "publish_message", "take_controller_message", "close_bus", "controller messages", "block", "multi-producer/single-consumer"),
    ("pcr-market-ticks", "MarketTickRing", "publish_tick", "take_tick", "close_feed", "market ticks", "coalesce", "multi-producer/single-consumer"),
    ("pcr-gps-samples", "GpsSampleRing", "publish_sample", "take_location_sample", "close_location", "GPS samples", "block", "single-producer/single-consumer"),
    ("pcr-build-events", "BuildEventRing", "report_build_event", "take_report_event", "close_reporting", "build events", "block", "multi-producer/single-consumer"),
    ("pcr-video-segments", "VideoSegmentRing", "submit_segment", "take_upload_segment", "finish_encoding", "video segments", "block", "multi-producer/single-consumer"),
    ("pcr-sensor-fusion", "SensorFusionRing", "publish_tagged_sample", "take_fusion_sample", "close_sources", "tagged sensor samples", "block", "multi-producer/single-consumer"),
    ("pcr-print-pipeline", "PrintPipelineRing", "enqueue_print_payload", "take_print_payload", "close_printers", "print payloads", "block", "multi-producer/single-consumer"),
    ("pcr-payment-events", "PaymentEventRing", "publish_payment_event", "take_audit_event", "close_payments", "payment events", "reject", "multi-producer/single-consumer"),
    ("pcr-file-watch", "FileWatchRing", "publish_change", "take_index_change", "close_watcher", "filesystem changes", "drop_oldest", "single-producer/single-consumer"),
    ("pcr-robot-commands", "RobotCommandRing", "submit_command", "take_controller_command", "close_planner", "robot commands", "reject", "single-producer/single-consumer"),
    ("pcr-support-notifications", "SupportNotificationRing", "publish_ticket_update", "take_dispatch_update", "close_dispatch", "ticket updates", "block", "multi-producer/multi-consumer"),
    ("pcr-weather-station", "WeatherStationRing", "publish_sample", "take_aggregate_sample", "close_station", "weather samples", "drop_oldest", "single-producer/single-consumer"),
    ("pcr-game-input", "GameInputRing", "publish_input", "take_tick_input", "close_simulation", "game input events", "drop_oldest", "single-producer/single-consumer"),
    ("pcr-warehouse-scans", "WarehouseScanRing", "submit_scan", "take_inventory_scan", "close_scanners", "parcel scans", "block", "multi-producer/single-consumer"),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum {{
struct RingStatistics {{ std::size_t accepted = 0; std::size_t delivered = 0; std::size_t dropped = 0; std::size_t pending = 0; bool closed = false; }};
class {s.class_name} {{
public:
  explicit {s.class_name}(std::size_t capacity);
  bool {s.publish}(int event_id); std::optional<int> {s.consume}(); void {s.close}();
  bool is_closed() const; std::size_t pending() const; RingStatistics statistics() const;
private:
  const std::size_t capacity_; mutable std::mutex mutex_; std::condition_variable not_empty_, not_full_;
  std::deque<int> events_; std::size_t accepted_ = 0, delivered_ = 0, dropped_ = 0; bool closed_ = false;
}};
}}  // namespace curriculum
#endif
'''


def _reference(s: TaskSpec) -> str:
    full = {
        "block": "not_full_.wait(lock, [this] { return closed_ || events_.size() < capacity_; }); if (closed_) return false;",
        "reject": "if (events_.size() == capacity_) return false;",
        "drop_oldest": "if (events_.size() == capacity_) { events_.pop_front(); ++dropped_; }",
        "coalesce": "if (events_.size() == capacity_) { events_.back() = event_id; ++dropped_; return true; }",
    }[s.policy]
    return f'''#include "task.h"
#include <stdexcept>
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{ if (!capacity_) throw std::invalid_argument("capacity must be positive"); }}
bool {s.class_name}::{s.publish}(int event_id) {{ if (event_id <= 0) return false; std::unique_lock<std::mutex> lock(mutex_); if (closed_) return false; {full} events_.push_back(event_id); ++accepted_; lock.unlock(); not_empty_.notify_one(); return true; }}
std::optional<int> {s.class_name}::{s.consume}() {{ std::unique_lock<std::mutex> lock(mutex_); not_empty_.wait(lock, [this] {{ return closed_ || !events_.empty(); }}); if (events_.empty()) return std::nullopt; int event_id = events_.front(); events_.pop_front(); ++delivered_; lock.unlock(); not_full_.notify_all(); return event_id; }}
void {s.class_name}::{s.close}() {{ std::lock_guard<std::mutex> lock(mutex_); closed_ = true; not_empty_.notify_all(); not_full_.notify_all(); }}
bool {s.class_name}::is_closed() const {{ std::lock_guard<std::mutex> lock(mutex_); return closed_; }}
std::size_t {s.class_name}::pending() const {{ std::lock_guard<std::mutex> lock(mutex_); return events_.size(); }}
RingStatistics {s.class_name}::statistics() const {{ std::lock_guard<std::mutex> lock(mutex_); return {{accepted_, delivered_, dropped_, events_.size(), closed_}}; }}
}}  // namespace curriculum
'''


def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{}}
bool {s.class_name}::{s.publish}(int) {{ return false; }} std::optional<int> {s.class_name}::{s.consume}() {{ return std::nullopt; }} void {s.class_name}::{s.close}() {{}}
bool {s.class_name}::is_closed() const {{ return false; }} std::size_t {s.class_name}::pending() const {{ return 0; }} RingStatistics {s.class_name}::statistics() const {{ return {{}}; }}
}}  // namespace curriculum
'''


def _test(s: TaskSpec, hidden: bool) -> str:
    if not hidden:
        full = "true" if s.policy in {"drop_oldest", "coalesce"} else "false"
        first = 2 if s.policy == "drop_oldest" else 1
        return f'''#include "task.h"
#include <optional>
#include <stdexcept>
int main() {{ int failures=0; const auto check=[&](bool ok){{ if (!ok) ++failures; }}; try {{ curriculum::{s.class_name} invalid(0); check(false); }} catch (const std::invalid_argument&) {{}}
  curriculum::{s.class_name} ring(2); check(!ring.{s.publish}(0)); check(ring.{s.publish}(1)); check(ring.{s.publish}(2)); check(ring.{s.publish}(3)=={full}); check(ring.{s.consume}()==std::optional<int>({first}));
  ring.{s.close}(); check(ring.is_closed()); check(!ring.{s.publish}(4)); while(ring.{s.consume}()){{}} check(!ring.{s.consume}()); return failures ? 1 : 0; }}
'''
    blocked = f'''std::promise<void> started; auto ready=started.get_future(); auto producer=std::async(std::launch::async,[&]{{ started.set_value(); return ring.{s.publish}(2); }}); ready.wait(); check(ring.{s.consume}()==std::optional<int>(1)); check(producer.get()); check(ring.{s.consume}()==std::optional<int>(2));''' if s.policy == "block" else f'''check(ring.{s.publish}(2)=={'false' if s.policy == 'reject' else 'true'});'''
    return f'''#include "task.h"
#include <future>
#include <optional>
int main() {{ int failures=0; const auto check=[&](bool ok){{ if (!ok) ++failures; }}; curriculum::{s.class_name} ring(1); check(ring.{s.publish}(1)); {blocked}
  curriculum::{s.class_name} closing(2); auto waiter=std::async(std::launch::async,[&]{{ return closing.{s.consume}(); }}); closing.{s.close}(); check(!waiter.get());
  curriculum::{s.class_name} trace(3); for(int value=1; value<=30; ++value) {{ check(trace.{s.publish}(value)); if(value%3==0) check(trace.{s.consume}()); }} trace.{s.close}(); while(trace.{s.consume}()){{}} const auto stats=trace.statistics(); check(stats.pending==0U && stats.closed); return failures ? 1 : 0; }}
'''


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(producer_consumer_ring_curriculum LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
find_package(Threads REQUIRED)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  target_link_libraries(${target} PRIVATE Threads::Threads)
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_custom_target(test_task ALL DEPENDS task_visible task_hidden COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure)
'''


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots = []
    for s in TASKS:
        root = out / s.task_id
        config = {"authors": ["w8-biayn"], "blurb": f"A {s.policy} bounded producer-consumer ring for {s.noun}.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "New task-specific producer-consumer API; not derived from an official Aider Polyglot benchmark task or tests."}
        policy = {"block": "blocks when full", "reject": "rejects a full-ring publication without mutation", "drop_oldest": "drops exactly the oldest retained entry when full", "coalesce": "replaces the newest pending entry when full"}[s.policy]
        files = {
            ".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local producer-consumer ring diagnostic about {s.noun}.\n",
            ".docs/instructions.md": f"# Instructions\n\nImplement `{s.class_name}`, a thread-safe bounded ring for {s.noun}. It supports {s.cardinality}. Capacity must be positive and nonpositive event IDs are rejected. `{s.publish}(event_id)` {policy}. `{s.consume}()` waits while empty and returns no value only after `{s.close}()` and full draining. Closure is idempotent, wakes blocked participants, and never discards accepted entries. Delivery is FIFO for retained entries. `statistics()` reports accepted, delivered, dropped, pending, and closure state.\n",
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": "[visible]\ndescription = \"task API, validation, overflow policy, FIFO, and closure\"\n\n[hidden]\ndescription = \"capacity-one coordination, close wakeup, wraparound traces, counters, and sanitizer execution\"\n",
            "task.h": _header(s), "task.cpp": _starter(s), ".meta/example.h": _header(s), ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake(),
        }
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    for root in (out / s.task_id for s in TASKS):
        with tempfile.TemporaryDirectory(prefix="pcr-curriculum-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied)
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={copied / '.meta' / 'example.cpp'}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format producer-consumer-ring curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} producer-consumer-ring curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
