# XOR Linked List Curriculum: Topic 1, Subtask 7

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This is the seventh subtask under **Linked Structure Invariants**. It teaches
the predecessor-XOR-successor traversal invariant, but it deliberately uses
stable slot indices rather than XORing native pointer addresses.

## Representation Safety Boundary

Do not author tasks that XOR raw C++ pointers. Pointer-to-integer conversion,
integer bit manipulation, and conversion back make a poor portability and
sanitizer target. Instead, use a fixed or growable slot arena. Each live node
has a nonzero stable `SlotId`; its link field is:

```text
link = previous_slot_id XOR next_slot_id
```

Traversal recovers the next slot from the previous slot and the current node's
link. A slot generation may be included in public handles to detect stale IDs
after slot reuse. This retains the intended invariant without relying on raw
pointer-address tricks.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

XOR-list explanations and isolated implementation examples are available
online, but there is no ready 20-task C++ corpus with consistent starter code,
oracle, licensing, and sanitizer behavior. External material is useful for
private concept study or source discovery only and needs explicit license and
semantic-contamination review.

The tasks below therefore materialize as newly authored C++17 roots using the
safe index-XOR representation. Their interfaces, tests, reference
implementations, and provenance must be created in-repo and pass the normal
original-task admission process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `xor-embedded-playlist` | Embedded playlist | Add, remove, and move compact track records by stable handle. |
| `xor-device-event-log` | Device event log | Append, prune, and traverse compact event records in either direction. |
| `xor-firmware-task-chain` | Firmware task chain | Schedule, cancel, and inspect adjacent low-memory task records. |
| `xor-sensor-sample-history` | Sensor-sample history | Retain a bounded history, discard old samples, and navigate neighbors. |
| `xor-train-car-store` | Train-car store | Attach, detach, and relocate compact car records by car ID. |
| `xor-radio-station-list` | Radio station list | Add, remove, and seek next or previous preset records. |
| `xor-print-job-store` | Print-job store | Submit, cancel, and rotate through low-memory print jobs. |
| `xor-packet-reassembly-order` | Packet reassembly order | Insert or discard packet IDs and walk adjacent retained packets. |
| `xor-recipe-step-chain` | Recipe-step chain | Insert, remove, and reorder compact recipe steps. |
| `xor-route-waypoint-store` | Route waypoint store | Add, remove, and navigate route waypoints by stable ID. |
| `xor-chat-message-history` | Chat-message history | Append, delete, and page through retained message IDs in both directions. |
| `xor-inventory-pick-chain` | Inventory pick chain | Relocate or cancel warehouse picks while preserving handle validity. |
| `xor-card-game-turns` | Card-game turns | Join, leave, and move through a compact circular turn sequence. |
| `xor-document-revisions` | Document revisions | Insert or discard revisions and navigate predecessor or successor revisions. |
| `xor-parking-queue` | Parking queue | Arrive, depart, and inspect neighboring vehicle records. |
| `xor-notification-history` | Notification history | Add, dismiss, and walk compact notification records. |
| `xor-support-ticket-order` | Support-ticket order | Open, close, and reposition tickets by priority handle. |
| `xor-file-block-chain` | File-block chain | Link, unlink, and seek neighboring logical file blocks. |
| `xor-museum-tour` | Museum tour | Edit a compact waypoint sequence and preserve current-position navigation. |
| `xor-delivery-stop-chain` | Delivery stop chain | Insert, remove, and reverse a short range of delivery stops. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a textbook
XOR-list node API as the visible assignment. The observable operations,
duplicate/invalid-input policy, handle semantics, and edge cases must
materially differ between roots.

Use integer slot IDs only. The scaffold and reference must forbid raw pointer
XOR, `reinterpret_cast`-based link arithmetic, and pointer/integer address
encoding. For each task, author a documented provenance record, starter
header/source pair, independent reference implementation, visible examples,
hidden Catch tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- empty and singleton structures;
- forward and reverse traversal from the same stored links;
- insertion or removal at head, tail, and middle positions;
- recovery of the next slot from `previous XOR current.link`;
- slot reuse and stale-handle rejection when the public API exposes handles;
- zero/sentinel slot behavior and invalid slot IDs;
- repeated relocation, deletion, and circular-navigation behavior where
  applicable;
- long seeded mutation sequences checked against a vector/deque oracle.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
