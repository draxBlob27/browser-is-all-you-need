"""Materialize newly-authored bounded blocking queue Aider curriculum tasks."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/bounded-blocking-queue")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BOUNDED_BLOCKING_QUEUE_CURRICULUM.md"

@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    submit: str
    take: str
    close: str
    noun: str
    feature: str
    feature_method: str

_RAW = (
    ("bbq-print-dispatch", "PrintDispatcher", "submit_print_job", "take_next_print", "close_dispatch", "print jobs", "stats", "statistics"),
    ("bbq-image-upload", "ImageUploadPipeline", "submit_upload", "take_upload", "close_uploads", "upload requests", "batch", "drain_upload_batch"),
    ("bbq-telemetry-ingest", "TelemetryIngest", "submit_reading", "take_reading", "close_ingest", "telemetry readings", "batch", "drain_ordered_batch"),
    ("bbq-audio-processing", "AudioProcessor", "submit_frame", "take_frame", "end_stream", "audio frames", "stats", "stream_state"),
    ("bbq-log-writer", "LogWriterQueue", "append_record", "take_record", "close_writer", "log records", "stats", "flush_statistics"),
    ("bbq-order-kitchen", "KitchenOrderQueue", "submit_order", "take_order", "close_service", "kitchen orders", "batch", "take_order_batch"),
    ("bbq-build-worker-pool", "BuildWorkerPool", "submit_build", "take_build", "close_submissions", "build requests", "stats", "work_statistics"),
    ("bbq-email-delivery", "EmailDeliveryQueue", "queue_email", "take_email", "close_delivery", "email requests", "cancel", "cancel_email"),
    ("bbq-document-indexer", "DocumentIndexerQueue", "submit_document", "take_document", "close_indexing", "document IDs", "stats", "index_statistics"),
    ("bbq-network-message-pump", "NetworkMessagePump", "submit_message", "take_message", "close_input", "network messages", "batch", "drain_messages"),
    ("bbq-customer-support", "SupportTicketIntake", "submit_ticket", "take_ticket", "close_intake", "support tickets", "stats", "intake_statistics"),
    ("bbq-sensor-fusion", "SensorFusionQueue", "submit_sample", "take_sample", "close_streams", "sensor samples", "batch", "take_fusion_batch"),
    ("bbq-video-transcode", "VideoTranscodeQueue", "submit_segment", "take_segment", "finish_uploads", "video segments", "stats", "transcode_statistics"),
    ("bbq-payment-retry", "PaymentRetryQueue", "submit_retry", "take_retry", "close_retries", "payment retries", "cancel", "cancel_retry"),
    ("bbq-route-calculation", "RouteCalculationQueue", "submit_route", "take_route", "close_requests", "route jobs", "stats", "pending_statistics"),
    ("bbq-database-write-behind", "WriteBehindQueue", "enqueue_mutation", "take_mutation", "close_writes", "database mutations", "batch", "flush_batch"),
    ("bbq-notification-delivery", "NotificationDeliveryQueue", "submit_notification", "take_notification", "close_notifications", "notifications", "stats", "delivery_statistics"),
    ("bbq-file-scan", "FileScanQueue", "submit_path", "take_path", "finish_walk", "file paths", "stats", "scan_statistics"),
    ("bbq-fraud-review", "FraudReviewQueue", "submit_review", "take_review", "close_reviews", "fraud reviews", "stats", "review_statistics"),
    ("bbq-warehouse-pick", "WarehousePickQueue", "submit_pick", "take_pick", "close_picks", "warehouse picks", "batch", "take_pick_batch"),
)
TASKS = tuple(TaskSpec(*row) for row in _RAW)

def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def _declaration(s: TaskSpec) -> str:
    if s.feature == "batch": return f"std::vector<int> {s.feature_method}(std::size_t limit);"
    if s.feature == "cancel": return f"bool {s.feature_method}(int request_id);"
    return f"QueueStatistics {s.feature_method}() const;"

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
struct QueueStatistics {{ std::size_t accepted = 0; std::size_t dispatched = 0; std::size_t pending = 0; bool closed = false; }};
class {s.class_name} {{ public:
 explicit {s.class_name}(std::size_t capacity); bool {s.submit}(int request_id); std::optional<int> {s.take}(); void {s.close}(); bool is_closed() const; std::size_t pending() const; {_declaration(s)}
private:
 const std::size_t capacity_; mutable std::mutex mutex_; std::condition_variable not_empty_; std::condition_variable not_full_; std::deque<int> requests_; std::size_t accepted_ = 0; std::size_t dispatched_ = 0; bool closed_ = false;
}}; }}  // namespace curriculum
#endif
'''

def _reference(s: TaskSpec) -> str:
    feature = (f'''std::vector<int> {s.class_name}::{s.feature_method}(std::size_t limit) {{ std::unique_lock<std::mutex> lock(mutex_); not_empty_.wait(lock, [this] {{ return closed_ || !requests_.empty(); }}); std::vector<int> out; while (limit-- && !requests_.empty()) {{ out.push_back(requests_.front()); requests_.pop_front(); ++dispatched_; }} lock.unlock(); not_full_.notify_all(); return out; }}''' if s.feature == "batch" else f'''bool {s.class_name}::{s.feature_method}(int id) {{ std::lock_guard<std::mutex> lock(mutex_); const auto it = std::find(requests_.begin(), requests_.end(), id); if (it == requests_.end()) return false; requests_.erase(it); not_full_.notify_one(); return true; }}''' if s.feature == "cancel" else f'''QueueStatistics {s.class_name}::{s.feature_method}() const {{ std::lock_guard<std::mutex> lock(mutex_); return {{accepted_, dispatched_, requests_.size(), closed_}}; }}''')
    return f'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{ if (!capacity) throw std::invalid_argument("capacity must be positive"); }}
bool {s.class_name}::{s.submit}(int id) {{ if (id <= 0) return false; std::unique_lock<std::mutex> lock(mutex_); not_full_.wait(lock, [this] {{ return closed_ || requests_.size() < capacity_; }}); if (closed_) return false; requests_.push_back(id); ++accepted_; lock.unlock(); not_empty_.notify_one(); return true; }}
std::optional<int> {s.class_name}::{s.take}() {{ std::unique_lock<std::mutex> lock(mutex_); not_empty_.wait(lock, [this] {{ return closed_ || !requests_.empty(); }}); if (requests_.empty()) return std::nullopt; int id = requests_.front(); requests_.pop_front(); ++dispatched_; lock.unlock(); not_full_.notify_one(); return id; }}
void {s.class_name}::{s.close}() {{ std::lock_guard<std::mutex> lock(mutex_); closed_ = true; not_empty_.notify_all(); not_full_.notify_all(); }}
bool {s.class_name}::is_closed() const {{ std::lock_guard<std::mutex> lock(mutex_); return closed_; }}
std::size_t {s.class_name}::pending() const {{ std::lock_guard<std::mutex> lock(mutex_); return requests_.size(); }}
{feature}
}}  // namespace curriculum
'''

def _starter(s: TaskSpec) -> str:
    feature = f"std::vector<int> {s.class_name}::{s.feature_method}(std::size_t) {{ return {{}}; }}" if s.feature == "batch" else f"bool {s.class_name}::{s.feature_method}(int) {{ return false; }}" if s.feature == "cancel" else f"QueueStatistics {s.class_name}::{s.feature_method}() const {{ return {{}}; }}"
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{}}
bool {s.class_name}::{s.submit}(int) {{ return false; }} std::optional<int> {s.class_name}::{s.take}() {{ return std::nullopt; }} void {s.class_name}::{s.close}() {{}}
bool {s.class_name}::is_closed() const {{ return false; }} std::size_t {s.class_name}::pending() const {{ return 0; }}
{feature}
}}  // namespace curriculum
'''

def _test(s: TaskSpec, hidden: bool) -> str:
    feature_setup = f"check(queue.{s.submit}(2)); check(queue.{s.submit}(3));" if s.feature in {"batch", "cancel"} else ""
    feature_assert = f"check(queue.{s.feature_method}(2) == std::vector<int>{{2, 3}});" if s.feature == "batch" else f"check(queue.{s.feature_method}(2)); check(!queue.{s.feature_method}(9)); check(queue.{s.take}() == std::optional<int>(3));" if s.feature == "cancel" else f"const auto stats = queue.{s.feature_method}(); check(stats.accepted == 1U && stats.dispatched == 1U && stats.pending == 0U && !stats.closed);"
    visible = f'''#include "task.h"
#include <optional>
#include <stdexcept>
#include <vector>
int main() {{ int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }}; try {{ curriculum::{s.class_name} invalid(0); check(false); }} catch (const std::invalid_argument&) {{}}
 curriculum::{s.class_name} queue(3); check(!queue.{s.submit}(0)); check(queue.{s.submit}(1)); check(queue.{s.take}() == std::optional<int>(1)); {feature_setup} {feature_assert} queue.{s.close}(); check(queue.is_closed()); check(!queue.{s.submit}(4)); while (queue.{s.take}()) {{}} check(!queue.{s.take}()); return failures ? 1 : 0; }}
'''
    hidden_source = f'''#include "task.h"
#include <algorithm>
#include <future>
#include <mutex>
#include <optional>
#include <thread>
#include <vector>
int main() {{ int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }}; curriculum::{s.class_name} queue(1); check(queue.{s.submit}(1));
 std::promise<void> started; auto ready = started.get_future(); auto producer = std::async(std::launch::async, [&] {{ started.set_value(); return queue.{s.submit}(2); }}); ready.wait(); check(queue.{s.take}() == std::optional<int>(1)); check(producer.get()); check(queue.{s.take}() == std::optional<int>(2));
 std::promise<void> consumer_started; auto consumer_ready = consumer_started.get_future(); auto consumer = std::async(std::launch::async, [&] {{ consumer_started.set_value(); return queue.{s.take}(); }}); consumer_ready.wait(); check(queue.{s.submit}(3)); check(consumer.get() == std::optional<int>(3)); auto closing = std::async(std::launch::async, [&] {{ return queue.{s.take}(); }}); queue.{s.close}(); check(!closing.get()); check(!queue.{s.submit}(4));
 curriculum::{s.class_name} shared(4); std::vector<int> received; std::mutex received_mutex; std::thread first([&] {{ for (int id : {{10, 12, 14}}) check(shared.{s.submit}(id)); }}); std::thread second([&] {{ for (int id : {{11, 13, 15}}) check(shared.{s.submit}(id)); }}); std::thread worker([&] {{ for (int i = 0; i < 6; ++i) {{ auto item = shared.{s.take}(); if (item) {{ std::lock_guard<std::mutex> lock(received_mutex); received.push_back(*item); }} }} }}); first.join(); second.join(); worker.join(); shared.{s.close}(); check(received.size() == 6U); std::sort(received.begin(), received.end()); check(received == std::vector<int>{{10, 11, 12, 13, 14, 15}}); return failures ? 1 : 0; }}
'''
    return hidden_source if hidden else visible

def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(bounded_blocking_queue_curriculum LANGUAGES CXX)
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
        root = out / s.task_id; header = _header(s)
        config = {"authors": ["w8-biayn"], "blurb": f"A bounded blocking FIFO for {s.noun}.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Newly authored task-specific queue API; not derived from an official Aider Polyglot benchmark task or its tests."}
        feature_contract = "The batch method waits for work and returns a FIFO batch." if s.feature == "batch" else "The cancellation method preserves FIFO order among remaining requests." if s.feature == "cancel" else "The statistics method reports accepted, dispatched, pending, and closure state."
        files = {".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local bounded blocking queue diagnostic about {s.noun}.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{s.class_name}`, a thread-safe bounded FIFO for {s.noun}. The constructor requires positive capacity. `{s.submit}(id)` rejects nonpositive IDs, blocks while full, and returns false if closure happens before admission. `{s.take}()` blocks while empty, returns queued requests FIFO, and returns no value only after closure and complete draining. `{s.close}()` is idempotent, wakes blocked producers and consumers, and does not discard accepted requests. {feature_contract}\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"task-specific API, capacity validation, FIFO, closure, and exposed feature\"\n\n[hidden]\ndescription = \"deterministic producer/consumer blocking, close wakeups, drain-after-close, multi-threaded no-loss trace, and sanitizer execution\"\n", "task.h": header, "task.cpp": _starter(s), ".meta/example.h": header, ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)

def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for root in (out / s.task_id for s in TASKS):
        with tempfile.TemporaryDirectory(prefix="bbq-curriculum-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format bounded-blocking-queue curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} bounded-blocking-queue curriculum tasks under {args.out}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
