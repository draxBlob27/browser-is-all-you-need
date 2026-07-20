# XOR Linked List Curriculum: Topic 1, Subtask 7

Status: v3 hard-rule remediation curriculum. The legacy generated family is
preserved under `.w8-biayn/data/aider-tasks/`; this document controls only the
parallel re-verification materialization. It does not claim dataset admission,
training authorization, or benchmark uplift.

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
- `docs/AIDER_SFT_SCOPE.md`

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

## Remediated Task Inventory

The legacy family used one add/remove/move template under 20 domain names. The
deterministic remedy retains the lexicographically smallest independently
justified root, replaces 16 roots with new IDs, and rejects three semantic
twins exposed by the v2 hard-rule re-audit. Shared safe XOR-slot mechanics are
permitted, but a superset payload/state object or shared policy-switch
reference is not. Public APIs, necessary state or algorithm,
selection/mutation rules, invalid behavior, reference control flow,
per-operation oracle, and compiled negative fixture must remain materially
different across every counted pair.

| Legacy ID | Disposition | V3 ID | Observable core capability |
|---|---|---|
| `xor-card-game-turns` | repair-in-place | `xor-card-game-turns` | quota ring, directional pass, and exhaustion deletion |
| `xor-chat-message-history` | replace | `xor-branching-chat-journal` | cursor branch pruning and deletion fallback |
| `xor-delivery-stop-chain` | replace | `xor-delivery-range-ledger` | inclusive reversal, detach, and atomic block insertion |
| `xor-device-event-log` | replace | `xor-bounded-event-window` | monotonic sequence admission and capacity eviction |
| `xor-document-revisions` | replace | `xor-revision-checkpoint-chain` | checkpoint rollback and checked tail squash |
| `xor-embedded-playlist` | replace | `xor-weighted-playback-ring` | smooth weighted selection over physical order |
| `xor-file-block-chain` | replace | `xor-block-offset-chain` | extent split, merge, and logical offset lookup |
| `xor-firmware-task-chain` | replace | `xor-dependency-ready-chain` | readiness selection and dependent-cancel guard |
| `xor-inventory-pick-chain` | replace | `xor-precedence-pick-chain` | precedence-preserving relocation and completion |
| `xor-museum-tour` | replace | `xor-accessible-tour-cursor` | access-mask filtered bidirectional cursor |
| `xor-notification-history` | replace | `xor-pinned-notification-feed` | stable pinned partition and unread scan |
| `xor-packet-reassembly-order` | replace | `xor-packet-gap-index` | interval merge, split, and first-gap query |
| `xor-parking-queue` | replace | `xor-neighbor-departure-line` | pre-removal neighbor receipt and adjacent swap |
| `xor-print-job-store` | replace | `xor-priority-print-spool` | stable priority bands and head dispatch |
| `xor-radio-station-list` | replace | `xor-band-preset-ring` | band-filtered circular seek and tune cursor |
| `xor-recipe-step-chain` | replace | `xor-recipe-dependency-chain` | multiple-prerequisite topological movement |
| `xor-route-waypoint-store` | replace | `xor-waypoint-distance-chain` | neighbor-delta Manhattan route aggregate |
| `xor-sensor-sample-history` | reject | — | policy-only bounded-window sibling of the device-event objective |
| `xor-support-ticket-order` | reject | — | stable-priority-band sibling of the print-spool objective |
| `xor-train-car-store` | reject | — | range reverse/detach sibling of the delivery-ledger objective |

## Materialization Requirements

Every counted root needs the exact task-specific C++17 API bound by its per-root remedy
specification. Do not expose a textbook XOR-list node API as the visible
assignment. The observable operations, owned state, mutation or selection
algorithm, duplicate/invalid-input policy, handle semantics, reference control
flow, and edge cases must materially differ between roots. All 136 unordered
v3 pairs and available related remediated DSA roots are screened dimension by
dimension from emitted docs, APIs, state, references, boundary tests,
operation traces, and negative substitutes; renamed, constants/policy-only,
and opposite-end clones fail closed through production-screen controls.

Use integer slot IDs only. The scaffold and reference must forbid raw pointer
XOR, `reinterpret_cast`-based link arithmetic, and pointer/integer address
encoding. For each task, author a documented provenance record, starter
header/source pair, independent reference implementation, visible examples,
hidden Catch tests, normal build, and fresh locked sanitizer build.

Private tests and owner checks must cover:

- empty and singleton structures;
- forward and reverse traversal from the same stored links;
- insertion or removal at head, tail, and middle positions;
- recovery of the next slot from `previous XOR current.link`;
- slot reuse and stale-handle rejection when the public API exposes handles;
- zero/sentinel slot behavior and invalid slot IDs;
- every task-specific selection, pruning, range, dependency, aggregate, or
  cursor transition named in the inventory;
- repeated mutation and stale-handle behavior where applicable;
- deterministic traces checked against independent vector/value behavior
  oracles after every operation, including return and complete ordering;
- one task-specific false substitute compiled under the reference warning
  policy and rejected by the same tests;
- production-screen rejection of a domain/identifier-renamed clone, a
  constants-or-policy-only clone, and an opposite-end-selection clone;
- prompt/role/reference mapping, all-pairs family duplication, related-family
  duplication, and semantic comparison against all bound official C++
  holdouts;
- clean normal and fresh ASan/UBSan reference runs in the pinned
  network-disabled C++ image with equal positive test discovery.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under
the current local task-authoring scope. Local completion ends at
`local_family_verified`; any future dataset intake requires a separately
approved admission contract.
