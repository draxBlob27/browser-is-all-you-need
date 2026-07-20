"""Materialize clean-room bounded blocking queue replacement tasks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_eval import WholeFormatError, build_prompt, load_task, parse_whole_file_blocks
from w8_biayn.integrations.moonlight_aider_task_sft import build_assistant_response, load_example_files_from_config

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/bounded-blocking-queue")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BOUNDED_BLOCKING_QUEUE_CURRICULUM.md"
FAMILY_ID = "aider-dsa-bounded-blocking-queue-v2"
MANIFEST_SCHEMA = "aider-bbq-materialization-v1"
REMEDY_HEADINGS = ("Identity", "Objective", "Public API", "Behavior table", "Implementation invariant", "Starter and reference", "Tests", "Files and metadata", "Build/oracle", "Family/contamination", "Optional dataset handoff", "Acceptance")
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset((
    "all-your-base", "allergies", "bank-account", "binary-search-tree", "circular-buffer", "clock",
    "complex-numbers", "crypto-square", "diamond", "dnd-character", "gigasecond", "grade-school",
    "kindergarten-garden", "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
    "perfect-numbers", "phone-number", "queen-attack", "robot-name", "space-age", "spiral-matrix",
    "sublist", "yacht", "zebra-puzzle",
))
MODE_MARKERS = {
    "stats": "QueueStatistics", "block_batch": "while (n-- && !requests_.empty())",
    "monotonic": "last_accepted_", "end_snapshot": "const auto n = requests_.size()",
    "close_drain": "closed_ = true; std::vector<int> out", "exact_batch": "requests_.size() < n",
    "ceiling": "submission_ceiling_", "replace": "*old = new_id", "unique": "unique_pending_.count",
    "try_submit": "requests_.size() >= capacity_", "cancel": "requests_.erase(it)",
    "source": "accepted_by_source_", "try_take": "if (requests_.empty()) return std::nullopt",
    "close_reason": "close_reason_ = reason", "resize": "capacity_ = n", "flush": "std::vector<int> out",
    "peek": "requests_.front()", "threshold": "requests_.size() >= n", "claim": "wanted",
    "discard": "requests_.clear()",
}


@dataclass(frozen=True)
class TaskSpec:
    legacy_id: str
    class_name: str
    submit: str
    take: str
    close: str
    noun: str
    mode: str
    method: str
    contract: str

    @property
    def task_id(self) -> str:
        return f"{self.legacy_id}-v2"


_ROWS = (
    ("bbq-print-dispatch", "PrintDispatcher", "submit_print_job", "take_next_print", "close_dispatch", "print jobs", "stats", "statistics", "statistics returns accepted, dispatched, pending, and closure state."),
    ("bbq-image-upload", "ImageUploadPipeline", "submit_upload", "take_upload", "close_uploads", "upload requests", "block_batch", "drain_upload_batch", "drain_upload_batch(limit) blocks for work then removes up to limit requests FIFO; zero is a no-op."),
    ("bbq-telemetry-ingest", "TelemetryIngest", "submit_reading", "take_reading", "close_ingest", "telemetry readings", "monotonic", "last_accepted_reading", "submit_reading rejects a positive reading no greater than the prior accepted reading; last_accepted_reading reports the latest accepted value."),
    ("bbq-audio-processing", "AudioProcessor", "submit_frame", "take_frame", "end_stream", "audio frames", "end_snapshot", "end_stream_snapshot", "end_stream_snapshot closes intake and returns the count that remains available for draining."),
    ("bbq-log-writer", "LogWriterQueue", "append_record", "take_record", "close_writer", "log records", "close_drain", "close_and_drain", "close_and_drain closes intake and returns all currently queued records FIFO."),
    ("bbq-order-kitchen", "KitchenOrderQueue", "submit_order", "take_order", "close_service", "kitchen orders", "exact_batch", "take_exact_order_batch", "take_exact_order_batch(count) waits for count orders; closure before that returns an empty batch and retains a partial batch."),
    ("bbq-build-worker-pool", "BuildWorkerPool", "submit_build", "take_build", "close_submissions", "build requests", "ceiling", "set_submission_ceiling", "set_submission_ceiling(total) bounds all future admissions even after capacity is freed."),
    ("bbq-email-delivery", "EmailDeliveryQueue", "queue_email", "take_email", "close_delivery", "email requests", "replace", "replace_queued_email", "replace_queued_email(old_id, new_id) replaces one pending ID in place and rejects absent, duplicate, or nonpositive values."),
    ("bbq-document-indexer", "DocumentIndexerQueue", "submit_document", "take_document", "close_indexing", "document IDs", "unique", "submit_unique_document", "submit_unique_document rejects an ID already pending; taking it permits a later resubmission."),
    ("bbq-network-message-pump", "NetworkMessagePump", "submit_message", "take_message", "close_input", "network messages", "try_submit", "try_submit_message", "try_submit_message never blocks and succeeds only while open with spare capacity."),
    ("bbq-customer-support", "SupportTicketIntake", "submit_ticket", "take_ticket", "close_intake", "support tickets", "cancel", "cancel_ticket", "cancel_ticket removes one pending ID while preserving the other FIFO positions."),
    ("bbq-sensor-fusion", "SensorFusionQueue", "submit_sample", "take_sample", "close_streams", "sensor samples", "source", "submit_from_source", "submit_from_source(source_id, sample_id) requires positive IDs and accepted_from_source reports successful admissions by source."),
    ("bbq-video-transcode", "VideoTranscodeQueue", "submit_segment", "take_segment", "finish_uploads", "video segments", "try_take", "try_take_segment", "try_take_segment never blocks and removes the next segment only when one is pending."),
    ("bbq-payment-retry", "PaymentRetryQueue", "submit_retry", "take_retry", "close_retries", "payment retries", "close_reason", "close_with_reason", "close_with_reason(reason) accepts one positive reason, closes intake, and exposes close_reason."),
    ("bbq-route-calculation", "RouteCalculationQueue", "submit_route", "take_route", "close_requests", "route jobs", "resize", "resize_capacity", "resize_capacity accepts a positive capacity no smaller than pending work and wakes blocked producers."),
    ("bbq-database-write-behind", "WriteBehindQueue", "enqueue_mutation", "take_mutation", "close_writes", "database mutations", "flush", "flush_batch", "flush_batch(limit) never blocks and removes up to limit mutations FIFO."),
    ("bbq-notification-delivery", "NotificationDeliveryQueue", "submit_notification", "take_notification", "close_notifications", "notifications", "peek", "wait_peek_notification", "wait_peek_notification blocks for work but does not remove the returned notification."),
    ("bbq-file-scan", "FileScanQueue", "submit_path", "take_path", "finish_walk", "file paths", "threshold", "take_when_at_least", "take_when_at_least(count) waits for count paths; after closure it drains up to count remaining paths."),
    ("bbq-fraud-review", "FraudReviewQueue", "submit_review", "take_review", "close_reviews", "fraud reviews", "claim", "claim_review", "claim_review(id) waits for and removes that exact pending ID, or returns no value after closure if it never arrives."),
    ("bbq-warehouse-pick", "WarehousePickQueue", "submit_pick", "take_pick", "close_picks", "warehouse picks", "discard", "discard_pending_picks", "discard_pending_picks removes every pending pick, returns the count, and wakes producers without closing intake."),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _decl(s: TaskSpec) -> str:
    return {
        "stats": f"QueueStatistics {s.method}() const;",
        "block_batch": f"std::vector<int> {s.method}(std::size_t limit);",
        "monotonic": f"std::optional<int> {s.method}() const;",
        "end_snapshot": f"std::size_t {s.method}();",
        "close_drain": f"std::vector<int> {s.method}();",
        "exact_batch": f"std::vector<int> {s.method}(std::size_t count);",
        "ceiling": f"bool {s.method}(std::size_t total);",
        "replace": f"bool {s.method}(int old_id, int new_id);",
        "unique": f"bool {s.method}(int document_id);",
        "try_submit": f"bool {s.method}(int message_id);",
        "cancel": f"bool {s.method}(int ticket_id);",
        "source": f"bool {s.method}(int source_id, int sample_id); std::size_t accepted_from_source(int source_id) const;",
        "try_take": f"std::optional<int> {s.method}();",
        "close_reason": f"bool {s.method}(int reason); int close_reason() const;",
        "resize": f"bool {s.method}(std::size_t capacity);",
        "flush": f"std::vector<int> {s.method}(std::size_t limit);",
        "peek": f"std::optional<int> {s.method}();",
        "threshold": f"std::vector<int> {s.method}(std::size_t count);",
        "claim": f"std::optional<int> {s.method}(int review_id);",
        "discard": f"std::size_t {s.method}();",
    }[s.mode]


def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>
#include <optional>
#include <unordered_map>
#include <unordered_set>
#include <vector>
namespace curriculum {{
struct QueueStatistics {{ std::size_t accepted = 0; std::size_t dispatched = 0; std::size_t pending = 0; bool closed = false; }};
class {s.class_name} {{
public:
    explicit {s.class_name}(std::size_t capacity);
    bool {s.submit}(int request_id);
    std::optional<int> {s.take}();
    void {s.close}();
    bool is_closed() const;
    std::size_t pending() const;
    {_decl(s)}
private:
    std::size_t capacity_;
    mutable std::mutex mutex_;
    std::condition_variable not_empty_;
    std::condition_variable not_full_;
    std::deque<int> requests_;
    std::unordered_set<int> unique_pending_;
    std::unordered_map<int, std::size_t> accepted_by_source_;
    std::size_t accepted_ = 0;
    std::size_t dispatched_ = 0;
    std::size_t submission_ceiling_ = static_cast<std::size_t>(-1);
    int last_accepted_ = 0;
    int close_reason_ = 0;
    bool closed_ = false;
}};
}}  // namespace curriculum
#endif
'''


def _pop() -> str:
    return "int id = requests_.front(); requests_.pop_front(); unique_pending_.erase(id); ++dispatched_;"


def _extension_reference(s: TaskSpec) -> str:
    p = _pop()
    m, c = s.method, s.class_name
    if s.mode == "stats": return f"QueueStatistics {c}::{m}() const {{ std::lock_guard<std::mutex> lock(mutex_); return {{accepted_, dispatched_, requests_.size(), closed_}}; }}"
    if s.mode == "block_batch": return f"std::vector<int> {c}::{m}(std::size_t n) {{ std::unique_lock<std::mutex> lock(mutex_); if (!n) return {{}}; not_empty_.wait(lock, [this] {{ return closed_ || !requests_.empty(); }}); std::vector<int> out; while (n-- && !requests_.empty()) {{ {p} out.push_back(id); }} lock.unlock(); not_full_.notify_all(); return out; }}"
    if s.mode == "monotonic": return f"std::optional<int> {c}::{m}() const {{ std::lock_guard<std::mutex> lock(mutex_); return last_accepted_ ? std::optional<int>(last_accepted_) : std::nullopt; }}"
    if s.mode == "end_snapshot": return f"std::size_t {c}::{m}() {{ std::lock_guard<std::mutex> lock(mutex_); closed_ = true; const auto n = requests_.size(); not_empty_.notify_all(); not_full_.notify_all(); return n; }}"
    if s.mode == "close_drain": return f"std::vector<int> {c}::{m}() {{ std::unique_lock<std::mutex> lock(mutex_); closed_ = true; std::vector<int> out; while (!requests_.empty()) {{ {p} out.push_back(id); }} lock.unlock(); not_empty_.notify_all(); not_full_.notify_all(); return out; }}"
    if s.mode == "exact_batch": return f"std::vector<int> {c}::{m}(std::size_t n) {{ std::unique_lock<std::mutex> lock(mutex_); if (!n) return {{}}; not_empty_.wait(lock, [this, n] {{ return closed_ || requests_.size() >= n; }}); if (requests_.size() < n) return {{}}; std::vector<int> out; while (n--) {{ {p} out.push_back(id); }} lock.unlock(); not_full_.notify_all(); return out; }}"
    if s.mode == "ceiling": return f"bool {c}::{m}(std::size_t n) {{ std::lock_guard<std::mutex> lock(mutex_); if (!n || n < accepted_) return false; submission_ceiling_ = n; return true; }}"
    if s.mode == "replace": return f"bool {c}::{m}(int old_id, int new_id) {{ if (new_id <= 0) return false; std::lock_guard<std::mutex> lock(mutex_); const auto old = std::find(requests_.begin(), requests_.end(), old_id); if (old == requests_.end() || std::find(requests_.begin(), requests_.end(), new_id) != requests_.end()) return false; *old = new_id; unique_pending_.erase(old_id); unique_pending_.insert(new_id); return true; }}"
    if s.mode == "unique": return f"bool {c}::{m}(int id) {{ if (id <= 0) return false; std::unique_lock<std::mutex> lock(mutex_); if (unique_pending_.count(id)) return false; not_full_.wait(lock, [this] {{ return closed_ || requests_.size() < capacity_; }}); if (closed_ || unique_pending_.count(id)) return false; requests_.push_back(id); unique_pending_.insert(id); ++accepted_; lock.unlock(); not_empty_.notify_one(); return true; }}"
    if s.mode == "try_submit": return f"bool {c}::{m}(int id) {{ if (id <= 0) return false; std::lock_guard<std::mutex> lock(mutex_); if (closed_ || requests_.size() >= capacity_) return false; requests_.push_back(id); ++accepted_; not_empty_.notify_one(); return true; }}"
    if s.mode == "cancel": return f"bool {c}::{m}(int id) {{ std::lock_guard<std::mutex> lock(mutex_); const auto it = std::find(requests_.begin(), requests_.end(), id); if (it == requests_.end()) return false; requests_.erase(it); unique_pending_.erase(id); not_full_.notify_one(); return true; }}"
    if s.mode == "source": return f"bool {c}::{m}(int source, int id) {{ if (source <= 0 || id <= 0) return false; std::unique_lock<std::mutex> lock(mutex_); not_full_.wait(lock, [this] {{ return closed_ || requests_.size() < capacity_; }}); if (closed_) return false; requests_.push_back(id); ++accepted_; ++accepted_by_source_[source]; lock.unlock(); not_empty_.notify_one(); return true; }} std::size_t {c}::accepted_from_source(int source) const {{ std::lock_guard<std::mutex> lock(mutex_); const auto it = accepted_by_source_.find(source); return it == accepted_by_source_.end() ? 0U : it->second; }}"
    if s.mode == "try_take": return f"std::optional<int> {c}::{m}() {{ std::lock_guard<std::mutex> lock(mutex_); if (requests_.empty()) return std::nullopt; {p} not_full_.notify_one(); return id; }}"
    if s.mode == "close_reason": return f"bool {c}::{m}(int reason) {{ if (reason <= 0) return false; std::lock_guard<std::mutex> lock(mutex_); if (closed_) return false; close_reason_ = reason; closed_ = true; not_empty_.notify_all(); not_full_.notify_all(); return true; }} int {c}::close_reason() const {{ std::lock_guard<std::mutex> lock(mutex_); return close_reason_; }}"
    if s.mode == "resize": return f"bool {c}::{m}(std::size_t n) {{ std::lock_guard<std::mutex> lock(mutex_); if (!n || n < requests_.size()) return false; capacity_ = n; not_full_.notify_all(); return true; }}"
    if s.mode == "flush": return f"std::vector<int> {c}::{m}(std::size_t n) {{ std::unique_lock<std::mutex> lock(mutex_); std::vector<int> out; while (n-- && !requests_.empty()) {{ {p} out.push_back(id); }} lock.unlock(); not_full_.notify_all(); return out; }}"
    if s.mode == "peek": return f"std::optional<int> {c}::{m}() {{ std::unique_lock<std::mutex> lock(mutex_); not_empty_.wait(lock, [this] {{ return closed_ || !requests_.empty(); }}); return requests_.empty() ? std::nullopt : std::optional<int>(requests_.front()); }}"
    if s.mode == "threshold": return f"std::vector<int> {c}::{m}(std::size_t n) {{ std::unique_lock<std::mutex> lock(mutex_); if (!n) return {{}}; not_empty_.wait(lock, [this, n] {{ return closed_ || requests_.size() >= n; }}); std::vector<int> out; while (n-- && !requests_.empty()) {{ {p} out.push_back(id); }} lock.unlock(); not_full_.notify_all(); return out; }}"
    if s.mode == "claim": return f"std::optional<int> {c}::{m}(int wanted) {{ if (wanted <= 0) return std::nullopt; std::unique_lock<std::mutex> lock(mutex_); not_empty_.wait(lock, [this, wanted] {{ return closed_ || std::find(requests_.begin(), requests_.end(), wanted) != requests_.end(); }}); const auto it = std::find(requests_.begin(), requests_.end(), wanted); if (it == requests_.end()) return std::nullopt; requests_.erase(it); unique_pending_.erase(wanted); ++dispatched_; lock.unlock(); not_full_.notify_one(); return wanted; }}"
    if s.mode == "discard": return f"std::size_t {c}::{m}() {{ std::lock_guard<std::mutex> lock(mutex_); const auto n = requests_.size(); requests_.clear(); unique_pending_.clear(); not_full_.notify_all(); return n; }}"
    raise AssertionError(s.mode)


def _reference(s: TaskSpec) -> str:
    monotonic = "if (id <= last_accepted_) return false;" if s.mode == "monotonic" else ""
    ceiling = "if (accepted_ >= submission_ceiling_) return false;" if s.mode == "ceiling" else ""
    update = "last_accepted_ = id;" if s.mode == "monotonic" else ""
    return f'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{ if (!capacity) throw std::invalid_argument("capacity must be positive"); }}
bool {s.class_name}::{s.submit}(int id) {{ if (id <= 0) return false; std::unique_lock<std::mutex> lock(mutex_); {monotonic} {ceiling} not_full_.wait(lock, [this] {{ return closed_ || requests_.size() < capacity_; }}); if (closed_) return false; {monotonic} {ceiling} requests_.push_back(id); ++accepted_; {update} lock.unlock(); not_empty_.notify_one(); return true; }}
std::optional<int> {s.class_name}::{s.take}() {{ std::unique_lock<std::mutex> lock(mutex_); not_empty_.wait(lock, [this] {{ return closed_ || !requests_.empty(); }}); if (requests_.empty()) return std::nullopt; {_pop()} lock.unlock(); not_full_.notify_one(); return id; }}
void {s.class_name}::{s.close}() {{ std::lock_guard<std::mutex> lock(mutex_); closed_ = true; not_empty_.notify_all(); not_full_.notify_all(); }}
bool {s.class_name}::is_closed() const {{ std::lock_guard<std::mutex> lock(mutex_); return closed_; }}
std::size_t {s.class_name}::pending() const {{ std::lock_guard<std::mutex> lock(mutex_); return requests_.size(); }}
{_extension_reference(s)}
}}  // namespace curriculum
'''


def _starter_extension(s: TaskSpec) -> str:
    c, m = s.class_name, s.method
    if s.mode == "stats": return f"QueueStatistics {c}::{m}() const {{ return {{}}; }}"
    if s.mode in {"block_batch", "exact_batch", "flush", "threshold"}: return f"std::vector<int> {c}::{m}(std::size_t) {{ return {{}}; }}"
    if s.mode == "close_drain": return f"std::vector<int> {c}::{m}() {{ return {{}}; }}"
    if s.mode in {"monotonic", "try_take", "peek"}: return f"std::optional<int> {c}::{m}() {{ return std::nullopt; }}"
    if s.mode == "claim": return f"std::optional<int> {c}::{m}(int) {{ return std::nullopt; }}"
    if s.mode in {"end_snapshot", "discard"}: return f"std::size_t {c}::{m}() {{ return 0; }}"
    if s.mode in {"ceiling", "resize"}: return f"bool {c}::{m}(std::size_t) {{ return false; }}"
    if s.mode in {"unique", "try_submit", "cancel", "close_reason"}: return f"bool {c}::{m}(int) {{ return false; }}"
    if s.mode == "replace": return f"bool {c}::{m}(int, int) {{ return false; }}"
    if s.mode == "source": return f"bool {c}::{m}(int, int) {{ return false; }} std::size_t {c}::accepted_from_source(int) const {{ return 0; }}"
    raise AssertionError(s.mode)


def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{}}
bool {s.class_name}::{s.submit}(int) {{ return false; }}
std::optional<int> {s.class_name}::{s.take}() {{ return std::nullopt; }}
void {s.class_name}::{s.close}() {{}}
bool {s.class_name}::is_closed() const {{ return false; }}
std::size_t {s.class_name}::pending() const {{ return 0; }}
{_starter_extension(s)}
}}  // namespace curriculum
'''


def _case(s: TaskSpec) -> str:
    m = s.method
    return {
        "stats": f"const auto x = queue.{m}(); check(x.accepted == 1U && x.dispatched == 1U && x.pending == 0U && !x.closed);",
        "block_batch": f"check(queue.{s.submit}(2)); check(queue.{s.submit}(3)); check(queue.{m}(2) == std::vector<int>{{2, 3}});",
        "monotonic": f"check(queue.{s.submit}(10)); check(!queue.{s.submit}(9)); check(queue.{m}() == std::optional<int>(10)); check(queue.{s.take}() == std::optional<int>(10));",
        "end_snapshot": f"check(queue.{s.submit}(2)); check(queue.{m}() == 1U); check(queue.{s.take}() == std::optional<int>(2));",
        "close_drain": f"check(queue.{s.submit}(2)); check(queue.{s.submit}(3)); check(queue.{m}() == std::vector<int>{{2, 3}});",
        "exact_batch": f"check(queue.{s.submit}(2)); check(queue.{s.submit}(3)); check(queue.{m}(2) == std::vector<int>{{2, 3}});",
        "ceiling": f"check(queue.{m}(2)); check(queue.{s.submit}(2)); check(queue.{s.take}() == std::optional<int>(2)); check(!queue.{s.submit}(3));",
        "replace": f"check(queue.{s.submit}(2)); check(queue.{m}(2, 3)); check(!queue.{m}(8, 4)); check(queue.{s.take}() == std::optional<int>(3));",
        "unique": f"check(queue.{m}(2)); check(!queue.{m}(2)); check(queue.{s.take}() == std::optional<int>(2)); check(queue.{m}(2));",
        "try_submit": f"curriculum::{s.class_name} q(1); check(q.{m}(2)); check(!q.{m}(3)); check(q.{s.take}() == std::optional<int>(2));",
        "cancel": f"check(queue.{s.submit}(2)); check(queue.{s.submit}(3)); check(queue.{m}(2)); check(!queue.{m}(9)); check(queue.{s.take}() == std::optional<int>(3));",
        "source": f"check(!queue.{m}(0, 2)); check(queue.{m}(7, 2)); check(queue.accepted_from_source(7) == 1U); check(queue.{s.take}() == std::optional<int>(2));",
        "try_take": f"check(!queue.{m}()); check(queue.{s.submit}(2)); check(queue.{m}() == std::optional<int>(2));",
        "close_reason": f"check(!queue.{m}(0)); check(queue.{m}(7)); check(queue.close_reason() == 7);",
        "resize": f"curriculum::{s.class_name} q(1); check(q.{s.submit}(2)); check(q.{m}(2)); check(q.{s.submit}(3));",
        "flush": f"check(queue.{s.submit}(2)); check(queue.{s.submit}(3)); check(queue.{m}(1) == std::vector<int>{{2}}); check(queue.{s.take}() == std::optional<int>(3));",
        "peek": f"check(queue.{s.submit}(2)); check(queue.{m}() == std::optional<int>(2)); check(queue.{s.take}() == std::optional<int>(2));",
        "threshold": f"check(queue.{s.submit}(2)); check(queue.{s.submit}(3)); check(queue.{m}(2) == std::vector<int>{{2, 3}});",
        "claim": f"check(queue.{s.submit}(2)); check(queue.{s.submit}(3)); check(queue.{m}(3) == std::optional<int>(3)); check(queue.{s.take}() == std::optional<int>(2));",
        "discard": f"check(queue.{s.submit}(2)); check(queue.{s.submit}(3)); check(queue.{m}() == 2U); check(queue.pending() == 0U);",
    }[s.mode]


def _test(s: TaskSpec, hidden: bool) -> str:
    visible = f'''#include "task.h"
#include <optional>
#include <stdexcept>
#include <vector>
int main() {{
    int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }};
    try {{ curriculum::{s.class_name} invalid(0); check(false); }} catch (const std::invalid_argument&) {{}}
    curriculum::{s.class_name} queue(3);
    check(!queue.{s.submit}(0)); check(queue.{s.submit}(1)); check(queue.{s.take}() == std::optional<int>(1));
    {_case(s)}
    queue.{s.close}(); check(queue.is_closed()); check(!queue.{s.submit}(99)); while (queue.{s.take}()) {{}} check(!queue.{s.take}());
    return failures ? 1 : 0;
}}
'''
    shared_trace = f'''std::vector<int> received; std::mutex received_mutex; std::atomic<int> producer_failures{{0}};
    std::thread first([&] {{ for (int id : {{10, 12, 14}}) if (!shared.{s.submit}(id)) ++producer_failures; }});
    std::thread second([&] {{ for (int id : {{11, 13, 15}}) if (!shared.{s.submit}(id)) ++producer_failures; }});'''
    if s.mode == "monotonic":
        shared_trace = f'''std::vector<int> received; std::mutex received_mutex; std::atomic<int> producer_failures{{0}}; std::mutex order_mutex; std::condition_variable order_changed; int next_id = 10;
    const auto submit_in_order = [&](int id) {{ std::unique_lock<std::mutex> lock(order_mutex); order_changed.wait(lock, [&] {{ return next_id == id; }}); lock.unlock(); if (!shared.{s.submit}(id)) ++producer_failures; lock.lock(); ++next_id; lock.unlock(); order_changed.notify_all(); }};
    std::thread first([&] {{ submit_in_order(10); submit_in_order(12); submit_in_order(14); }});
    std::thread second([&] {{ submit_in_order(11); submit_in_order(13); submit_in_order(15); }});'''
    hidden_source = f'''#include "task.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <future>
#include <mutex>
#include <optional>
#include <thread>
#include <vector>
int main() {{
    int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }};
    curriculum::{s.class_name} full(1); check(full.{s.submit}(1));
    std::promise<void> producer_started; auto producer_ready = producer_started.get_future();
    auto producer = std::async(std::launch::async, [&] {{ producer_started.set_value(); return full.{s.submit}(2); }});
    producer_ready.wait(); check(producer.wait_for(std::chrono::milliseconds(100)) == std::future_status::timeout);
    full.{s.close}(); check(!producer.get());
    curriculum::{s.class_name} empty(1); std::promise<void> consumer_started; auto consumer_ready = consumer_started.get_future();
    auto consumer = std::async(std::launch::async, [&] {{ consumer_started.set_value(); return empty.{s.take}(); }});
    consumer_ready.wait(); check(consumer.wait_for(std::chrono::milliseconds(100)) == std::future_status::timeout);
    check(empty.{s.submit}(3)); check(consumer.get() == std::optional<int>(3));
    curriculum::{s.class_name} shared(4); {shared_trace}
    std::thread worker([&] {{ for (int i = 0; i < 6; ++i) {{ auto item = shared.{s.take}(); if (item) {{ std::lock_guard<std::mutex> lock(received_mutex); received.push_back(*item); }} }} }});
    first.join(); second.join(); worker.join(); shared.{s.close}(); std::sort(received.begin(), received.end());
    check(producer_failures == 0); check(received == std::vector<int>{{10, 11, 12, 13, 14, 15}}); return failures ? 1 : 0;
}}
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
        root = out / s.task_id
        config = {"authors": ["w8-biayn"], "blurb": f"A bounded blocking FIFO for {s.noun} with {s.mode} semantics.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository v2 replacement diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 3, "family_id": FAMILY_ID, "semantic_profile": s.mode, "benchmark_separation": "Newly authored task-specific queue API; not derived from an official Aider Polyglot benchmark task or its tests."}
        files = {
            ".docs/introduction.md": f"# {s.class_name}\n\nA clean-room bounded blocking queue diagnostic for {s.noun}.\n",
            ".docs/instructions.md": f"# Instructions\n\nImplement {s.class_name}, a thread-safe bounded FIFO for {s.noun}. The constructor requires positive capacity. {s.submit}(id) rejects nonpositive IDs, blocks while full, and returns false if closure occurs before admission. {s.take}() blocks while empty, returns requests FIFO, and returns no value only after closure and complete draining. {s.close}() is idempotent, wakes blocked producers and consumers, and does not discard accepted requests. {s.contract}\n",
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": f"[visible]\ndescription = \"capacity validation, FIFO, closure, and {s.mode} contract\"\n\n[hidden]\ndescription = \"bounded producer and consumer blocking, close wakeups, multithread no-loss trace, and sanitizer execution\"\n",
            "task.h": _header(s), "task.cpp": _starter(s), ".meta/example.h": _header(s), ".meta/example.cpp": _reference(s),
            "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake(),
        }
        for relative, content in task_named_files(root, files).items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def _fail(code: str, detail: str = "") -> None:
    raise RuntimeError(f"{code}{': ' + detail if detail else ''}")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0" + path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail("unsafe_path", "empty or non-string path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        _fail("unsafe_path", value)
    return path.as_posix()


def _whole_format_code(task_dir: Path, content: str) -> str | None:
    task = load_task(task_dir)
    try:
        parsed = parse_whole_file_blocks(content)
    except WholeFormatError:
        return "whole_format_failed"
    return None if set(parsed) == set(task.editable_files) else "whole_format_failed"


def _semantic_screen() -> dict[str, str]:
    seen_modes: set[str] = set()
    seen_signatures: set[str] = set()
    signatures: dict[str, str] = {}
    for spec in TASKS:
        if spec.mode in seen_modes:
            _fail("duplicate_family", f"duplicate mode {spec.mode}")
        seen_modes.add(spec.mode)
        extension = _extension_reference(spec)
        marker = MODE_MARKERS[spec.mode]
        if marker not in extension:
            _fail("invariant_not_enforced", f"missing {marker} for {spec.task_id}")
        payload = "\n".join((spec.mode, _decl(spec), spec.contract, extension))
        signature = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if signature in seen_signatures:
            _fail("duplicate_family", f"semantic signature {spec.task_id}")
        seen_signatures.add(signature)
        signatures[spec.task_id] = f"sha256:{signature}"
    return signatures


def _benchmark_screen(root: Path) -> None:
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in sorted(root.rglob("*")) if path.is_file())
    normalized = corpus.lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", normalized):
            _fail("benchmark_id_overlap", slug)
    for forbidden in ("aider-ai/polyglot", "exercism c++ exercise", "upstream polyglot benchmark"):
        if forbidden in normalized:
            _fail("benchmark_content_overlap", forbidden)


def _verify_remedy_records(out: Path) -> None:
    remedy = out / ".state" / "remedy"
    records = {path.stem: path for path in remedy.glob("*.json")} if remedy.is_dir() else {}
    if set(records) != {spec.task_id for spec in TASKS}:
        _fail("remedy_spec_incomplete", "one record per replacement root is required")
    for task_id, record_path in records.items():
        record = json.loads(record_path.read_text(encoding="utf-8"))
        spec_path = remedy / f"{task_id}.md"
        if record.get("task_id") != task_id or record.get("disposition") != "replace" or not spec_path.is_file():
            _fail("remedy_disposition_conflict", task_id)
        spec_text = spec_path.read_text(encoding="utf-8")
        positions = [spec_text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", task_id)
        expected_hash = f"sha256:{hashlib.sha256(spec_text.encode('utf-8')).hexdigest()}"
        if record.get("remedy_spec_hash") != expected_hash:
            _fail("remedy_spec_incomplete", f"stale specification hash for {task_id}")


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    expected = {spec.task_id for spec in TASKS}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {len(expected)} roots, found {len(actual)}")
    if require_remedy:
        _verify_remedy_records(out)
    with tempfile.TemporaryDirectory(prefix="bbq-materialization-") as temporary:
        fresh = Path(temporary) / "fresh"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    signatures = _semantic_screen()
    manifest_tasks = []
    for task_id in sorted(expected):
        root = out / task_id
        config = json.loads((root / ".meta" / "config.json").read_text(encoding="utf-8"))
        files = config.get("files")
        if not isinstance(files, dict):
            _fail("unsafe_path", f"files map missing for {task_id}")
        solution = [_safe_relative(item) for item in files.get("solution", [])]
        tests = [_safe_relative(item) for item in files.get("test", [])]
        examples = [_safe_relative(item) for item in files.get("example", [])]
        if len(solution) != 2 or len(examples) != 2 or len(set(solution)) != 2:
            _fail("reference_map_failed", task_id)
        if set(solution) & (set(tests) | set(examples)) or any(name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt" for name in solution):
            _fail("unsafe_path", task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("reference_map_failed", task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        private = [*tests, *examples, "CMakeLists.txt", ".meta/provenance.json", ".meta/task_hidden_test.cpp"]
        if any(name in prompt for name in private):
            _fail("prompt_contract_incomplete", task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_code(root, answer) is not None:
            _fail("target_reference_mismatch", task_id)
        missing = f"{task.editable_files[0]}\n```cpp\n// incomplete\n```\n"
        extra = answer + "\nunknown.cpp\n```cpp\n// forbidden\n```\n"
        prose = "explanation\n" + answer
        if any(_whole_format_code(root, response) != "whole_format_failed" for response in (missing, extra, prose)):
            _fail("whole_format_failed", task_id)
        _benchmark_screen(root)
        manifest_tasks.append({"task_id": task_id, "tree_hash": _tree_hash(root), "semantic_signature": signatures[task_id]})
    manifest = {"schema_version": MANIFEST_SCHEMA, "family_id": FAMILY_ID, "task_count": len(manifest_tasks), "tasks": manifest_tasks, "screen": {"prompt_boundary": "pass", "reference_mapping": "pass", "duplicate_family": "pass", "benchmark_contamination": "pass"}}
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "materialization-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _count_discovered(output: str) -> int:
    match = re.search(r"Total Tests:\s*(\d+)", output)
    if not match: raise RuntimeError("test_discovery_failed")
    count = int(match.group(1))
    if not count: raise RuntimeError("zero_tests")
    return count


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    verify_core(out)
    receipts = []
    for root in (out / s.task_id for s in TASKS):
        receipt = {"task_id": root.name, "modes": {}}
        with tempfile.TemporaryDirectory(prefix="bbq-curriculum-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                configure = ["cmake", "-S", str(copied), "-B", str(build_dir), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={reference}", *flags]
                subprocess.run(configure, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                discovered = subprocess.run(["ctest", "--test-dir", str(build_dir), "-N"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                count = _count_discovered(discovered.stdout)
                executed = subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                receipt["modes"][name] = {"configure": configure, "discovered_tests": count, "ctest_output": executed.stdout}
        if receipt["modes"]["normal"]["discovered_tests"] != receipt["modes"]["sanitizer"]["discovered_tests"]: raise RuntimeError(f"sanitizer_test_count_mismatch: {root.name}")
        receipts.append(receipt)
    path = out / ".state" / "oracle-receipt.json"; path.parent.mkdir(parents=True, exist_ok=True)
    runtime = {
        "environment": os.environ.get("W8_BIAYN_ORACLE_RUNTIME", "host-prerequisite"),
        "image": os.environ.get("W8_BIAYN_ORACLE_IMAGE"),
        "compiler": subprocess.run(["c++", "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0],
        "cmake": subprocess.run(["cmake", "--version"], check=True, stdout=subprocess.PIPE, text=True).stdout.splitlines()[0],
    }
    path.write_text(json.dumps({"runtime": runtime, "tasks": receipts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format bounded-blocking-queue curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true"); parser.add_argument("--verify-core", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify_core: verify_core(args.out)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} bounded-blocking-queue curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
