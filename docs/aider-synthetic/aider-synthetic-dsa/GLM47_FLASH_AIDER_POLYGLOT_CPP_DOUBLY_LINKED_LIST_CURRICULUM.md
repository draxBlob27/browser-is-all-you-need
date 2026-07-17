# Doubly Linked List Curriculum: Topic 1, Subtask 1

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This is the first subtask under **Linked Structure Invariants**. Its aim is to
teach pointer-invariant reasoning through C++17 tasks whose visible contracts
are domain-specific. The official Aider Polyglot C++ `linked-list` task is a
permanent benchmark holdout. Do not copy it, its tests, its reference, its
prompts, or close semantic variants into SFT data.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

Direct doubly-linked-list exercises are available online, including
HackerRank's reverse-a-doubly-linked-list exercise, LeetCode's multilevel
doubly-linked-list exercise, and the Open Data Structures C++ `DLList`
discussion. They are useful for private concept study only. They are not a
drop-in SFT source inventory: the direct exercise shape is benchmark-adjacent,
and every external source would still require an explicit license and semantic
contamination review.

The tasks below therefore materialize as newly authored roots. Their required
behavior, C++ interface, tests, reference implementations, and provenance are
created in-repo and then pass the normal original-task admission process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `dll-tab-strip` | Tab strip | Open, activate, move, and close stable-ID tabs. |
| `dll-playlist-editor` | Playlist editor | Insert tracks before or after another track and move a selected range. |
| `dll-browser-history` | Browser history | Navigate backward and forward; visiting after back removes the forward branch. |
| `dll-train-consist` | Train consist | Attach, detach, and relocate named train cars. |
| `dll-revision-timeline` | Revision timeline | Undo and redo around a current revision; branch after rollback. |
| `dll-round-robin-scheduler` | Round-robin scheduler | Rotate jobs, cancel by ID, and inspect the current job. |
| `dll-elevator-stops` | Elevator stops | Add, cancel, and serve stops while preserving route order. |
| `dll-music-queue` | Music queue | Promote a queued song, remove it, and advance playback. |
| `dll-photo-carousel` | Photo carousel | Navigate, delete the current photo, and preserve the intended selection. |
| `dll-parking-line` | Parking line | Arrive, depart by license plate, and report adjacent vehicles. |
| `dll-print-spooler` | Print spooler | Submit, cancel, reprioritize, and serve print jobs. |
| `dll-meeting-agenda` | Meeting agenda | Reorder agenda items and retain a current discussion pointer. |
| `dll-text-line-cursor` | Text-line cursor | Insert or remove lines around a bidirectional cursor. |
| `dll-delivery-route` | Delivery route | Insert or remove a stop and reverse a contiguous route segment. |
| `dll-card-table-order` | Card-table turn order | Join or leave players and rotate turns in a circular variant. |
| `dll-museum-tour` | Museum tour | Edit waypoints and jump to next or previous accessible waypoint. |
| `dll-notification-feed` | Notification feed | Pin, unpin, dismiss, and navigate unread notifications. |
| `dll-warehouse-picks` | Warehouse pick chain | Relocate a pick task after a dependency and safely cancel a task. |
| `dll-book-shelf` | Book-shelf organizer | Move a book by ID, insert beside another book, and apply a duplicate policy. |
| `dll-support-tickets` | Support-ticket queue | Escalate or de-escalate tickets, close them, and retain an active-ticket cursor. |

## Materialization Requirements

Every candidate must have a distinct C++17 public API. For example, expose
`activate_tab(TabId)` or `relocate_car(CarId, CarId)` rather than generic
node-manipulation functions. Domain renaming alone is not enough: the set of
observable operations, invalid-input behavior, and edge cases must materially
differ between roots.

For each candidate, author:

1. a documented source/provenance record and task specification;
2. a starter header/source pair with the task-specific public API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. a normal build plus a fresh locked sanitizer build.

Hidden tests must exercise pointer-invariant failures:

- empty and singleton structures;
- insertion and removal at head, tail, and middle positions;
- repeated relocation or deletion;
- invalid or stale stable IDs;
- forward and backward traversal agreement;
- head with no predecessor, tail with no successor, and reciprocal `next` /
  `prev` links;
- randomized operation sequences checked against a simple vector/deque oracle.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A task judged to be a
close semantic copy of the official benchmark `linked-list` root must be
rejected from SFT and may only be retained as a separate internal diagnostic
candidate where permitted.
