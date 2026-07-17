"""Materialize the local Aider-format doubly-linked-list curriculum tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence


DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/doubly-linked-list")

# These are newly authored local diagnostic roots.  They deliberately retain
# different public verbs and observable contracts rather than importing an
# online linked-list exercise.
TASKS = (
    ("dll-playlist-editor", "PlaylistEditor", "Track", "insert_after", "remove_track", "relocate_after", "Insert tracks before or after another track and move a selected range."),
    ("dll-browser-history", "BrowserHistory", "Page", "visit", "forget_page", "revisit_after", "Navigate backward and forward; visiting after back removes the forward branch."),
    ("dll-train-consist", "TrainConsist", "Car", "attach_after", "detach_car", "relocate_after", "Attach, detach, and relocate named train cars."),
    ("dll-revision-timeline", "RevisionTimeline", "Revision", "commit_after", "discard_revision", "branch_after", "Undo and redo around a current revision; branch after rollback."),
    ("dll-round-robin-scheduler", "RoundRobinScheduler", "Job", "enqueue_after", "cancel_job", "rotate_after", "Rotate jobs, cancel by ID, and inspect the current job."),
    ("dll-elevator-stops", "ElevatorStops", "Stop", "add_after", "cancel_stop", "serve_after", "Add, cancel, and serve stops while preserving route order."),
    ("dll-music-queue", "MusicQueue", "Song", "queue_after", "remove_song", "promote_after", "Promote a queued song, remove it, and advance playback."),
    ("dll-photo-carousel", "PhotoCarousel", "Photo", "append_after", "delete_photo", "select_after", "Navigate, delete the current photo, and preserve the intended selection."),
    ("dll-parking-line", "ParkingLine", "Vehicle", "arrive_after", "depart_vehicle", "relocate_after", "Arrive, depart by license plate, and report adjacent vehicles."),
    ("dll-print-spooler", "PrintSpooler", "Job", "submit_after", "cancel_job", "reprioritize_after", "Submit, cancel, reprioritize, and serve print jobs."),
    ("dll-meeting-agenda", "MeetingAgenda", "Item", "add_after", "remove_item", "reorder_after", "Reorder agenda items and retain a current discussion pointer."),
    ("dll-text-line-cursor", "TextLineCursor", "Line", "insert_after", "erase_line", "move_cursor_after", "Insert or remove lines around a bidirectional cursor."),
    ("dll-delivery-route", "DeliveryRoute", "Stop", "insert_after", "remove_stop", "reverse_after", "Insert or remove a stop and reverse a contiguous route segment."),
    ("dll-card-table-order", "CardTableOrder", "Player", "join_after", "leave_player", "rotate_after", "Join or leave players and rotate turns in a circular variant."),
    ("dll-museum-tour", "MuseumTour", "Waypoint", "add_after", "remove_waypoint", "jump_after", "Edit waypoints and jump to next or previous accessible waypoint."),
    ("dll-notification-feed", "NotificationFeed", "Notification", "publish_after", "dismiss_notification", "pin_after", "Pin, unpin, dismiss, and navigate unread notifications."),
    ("dll-warehouse-picks", "WarehousePicks", "Pick", "add_after", "cancel_pick", "relocate_after", "Relocate a pick task after a dependency and safely cancel a task."),
    ("dll-book-shelf", "BookShelf", "Book", "place_after", "remove_book", "move_after", "Move a book by ID, insert beside another book, and apply a duplicate policy."),
    ("dll-support-tickets", "SupportTickets", "Ticket", "open_after", "close_ticket", "escalate_after", "Escalate or de-escalate tickets, close them, and retain an active-ticket cursor."),
)


def _write(path: Path, text: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != text and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _header(cls: str, entity: str, add: str, remove: str, move: str) -> str:
    guard = f"{cls.upper()}_H"
    return f'''#ifndef {guard}\n#define {guard}\n\n#include <vector>\n\nnamespace curriculum {{\n\nusing {entity}Id = int;\n\nclass {cls} {{\npublic:\n    {cls}() = default;\n    {cls}(const {cls}&) = delete;\n    {cls}& operator=(const {cls}&) = delete;\n    ~{cls}();\n\n    bool {add}({entity}Id id, {entity}Id after_id = 0);\n    bool {remove}({entity}Id id);\n    bool {move}({entity}Id id, {entity}Id after_id);\n    std::vector<{entity}Id> order() const;\n    std::vector<{entity}Id> reverse_order() const;\n\nprivate:\n    struct Node {{ {entity}Id id; Node* prev; Node* next; }};\n    Node* head_ = nullptr;\n    Node* tail_ = nullptr;\n    Node* find({entity}Id id) const;\n    void unlink(Node* node);\n    void insert_after(Node* node, Node* after);\n}};\n\n}}  // namespace curriculum\n\n#endif\n'''


def _reference(cls: str, entity: str, add: str, remove: str, move: str) -> str:
    return f'''#include "task.h"\n\nnamespace curriculum {{\n\n{cls}::~{cls}() {{ while (head_) {{ Node* next = head_->next; delete head_; head_ = next; }} }}\n\nbool {cls}::{add}({entity}Id id, {entity}Id after_id) {{\n    if (id <= 0 || find(id)) return false;\n    Node* after = after_id == 0 ? tail_ : find(after_id);\n    if (after_id != 0 && !after) return false;\n    Node* node = new Node{{id, nullptr, nullptr}};\n    insert_after(node, after);\n    return true;\n}}\n\nbool {cls}::{remove}({entity}Id id) {{ Node* node = find(id); if (!node) return false; unlink(node); delete node; return true; }}\nbool {cls}::{move}({entity}Id id, {entity}Id after_id) {{\n    Node* node = find(id); Node* after = find(after_id);\n    if (!node || !after) return false;\n    if (node == after) return true;\n    unlink(node);\n    insert_after(node, after);\n    return true;\n}}\n\nstd::vector<{entity}Id> {cls}::order() const {{ std::vector<{entity}Id> out; for (Node* n = head_; n; n = n->next) out.push_back(n->id); return out; }}\nstd::vector<{entity}Id> {cls}::reverse_order() const {{ std::vector<{entity}Id> out; for (Node* n = tail_; n; n = n->prev) out.push_back(n->id); return out; }}\n{cls}::Node* {cls}::find({entity}Id id) const {{ for (Node* n = head_; n; n = n->next) if (n->id == id) return n; return nullptr; }}\nvoid {cls}::unlink(Node* node) {{ if (node->prev) node->prev->next = node->next; else head_ = node->next; if (node->next) node->next->prev = node->prev; else tail_ = node->prev; node->prev = node->next = nullptr; }}\nvoid {cls}::insert_after(Node* node, Node* after) {{ if (!after) {{ node->next = head_; if (head_) head_->prev = node; else tail_ = node; head_ = node; return; }} node->prev = after; node->next = after->next; if (after->next) after->next->prev = node; else tail_ = node; after->next = node; }}\n\n}}  // namespace curriculum\n'''


def _starter(cls: str, entity: str, add: str, remove: str, move: str) -> str:
    return f'''#include "task.h"\n\nnamespace curriculum {{\n\n{cls}::~{cls}() = default;\nbool {cls}::{add}({entity}Id, {entity}Id) {{ return false; }}\nbool {cls}::{remove}({entity}Id) {{ return false; }}\nbool {cls}::{move}({entity}Id, {entity}Id) {{ return false; }}\nstd::vector<{entity}Id> {cls}::order() const {{ return {{}}; }}\nstd::vector<{entity}Id> {cls}::reverse_order() const {{ return {{}}; }}\n{cls}::Node* {cls}::find({entity}Id) const {{ return nullptr; }}\nvoid {cls}::unlink(Node*) {{}}\nvoid {cls}::insert_after(Node*, Node*) {{}}\n\n}}  // namespace curriculum\n'''


def _test(cls: str, entity: str, add: str, remove: str, move: str) -> str:
    return f'''#include "task.h"\n#include <algorithm>\n#include <iostream>\n#include <vector>\n\nint main() {{\n    curriculum::{cls} task;\n    int failures = 0;\n    const auto check = [&](bool value) {{ if (!value) ++failures; }};\n    check(!task.{add}(0));\n    check(task.{add}(10));\n    check(task.{add}(20, 10));\n    check(task.{add}(30, 20));\n    check(!task.{add}(20));\n    check(task.{move}(30, 10));\n    check(task.order() == std::vector<curriculum::{entity}Id>{{10, 30, 20}});\n    check(task.{remove}(30));\n    check(task.order() == std::vector<curriculum::{entity}Id>{{10, 20}});\n    check(task.reverse_order() == std::vector<curriculum::{entity}Id>{{20, 10}});\n    check(!task.{remove}(30));\n    return failures == 0 ? 0 : 1;\n}}\n'''


def build(out: Path, force: bool = False) -> tuple[Path, ...]:
    roots = []
    for task_id, cls, entity, add, remove, move, contract in TASKS:
        root = out / task_id
        header = _header(cls, entity, add, remove, move)
        config = {"authors": ["w8-biayn"], "blurb": contract, "files": {"solution": ["task.h", "task.cpp"], "test": ["task_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        files = {
            ".docs/introduction.md": f"# {cls}\n\nA newly authored local doubly-linked-list diagnostic task.\n",
            ".docs/instructions.md": f"# Instructions\n\nImplement `{cls}`. {contract}\n\nIDs must be positive and unique. `{add}` inserts after `after_id` (or at the head when it is zero); `{remove}` and `{move}` reject stale IDs without changing the structure. `order()` and `reverse_order()` must agree after every operation.\n",
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps({"curriculum_document": "docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DOUBLY_LINKED_LIST_CURRICULUM.md", "curriculum_task_id": task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1}, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": "[operations]\ndescription = \"domain operations and stable IDs\"\n\n[invariants]\ndescription = \"forward and backward traversal agreement\"\n",
            "task.h": header,
            "task.cpp": _starter(cls, entity, add, remove, move),
            ".meta/example.h": header,
            ".meta/example.cpp": _reference(cls, entity, add, remove, move),
            "task_test.cpp": _test(cls, entity, add, remove, move),
            "CMakeLists.txt": "cmake_minimum_required(VERSION 3.16)\nproject(dll_curriculum_task LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)\nadd_executable(task_test task.cpp task_test.cpp)\ntarget_compile_options(task_test PRIVATE -Wall -Wextra -Wpedantic -Werror)\nadd_custom_target(test_task ALL DEPENDS task_test COMMAND task_test)\n",
        }
        files = task_named_files(root, files)
        for relative, content in files.items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the local doubly-linked-list Aider curriculum.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    print(f"Wrote {len(roots)} tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
