# Producer-Consumer Ring Curriculum: Topic 1, Producer-Consumer Rings

Status: locally remediated v2 curriculum. The legacy 20-root renamed-deque
family remains preserved as audit input. The parallel v2 roots are local
verification material, not admitted SFT roots or an online dataset.

This curriculum combines ring-buffer cursor invariants with producer/consumer
synchronization. It teaches bounded delivery, FIFO ordering, wraparound,
backpressure or drop policy, closure, and safe ownership transfer.

Unless a task explicitly says otherwise, implementations may use a mutex and
condition variables; lock-free algorithms are not required. A task that needs
single-producer/single-consumer atomics must explicitly define its memory-order
contract and receive a separate concurrency review.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

## Online Material Status

Producer-consumer ring examples are available online, but there is no ready
20-task C++ corpus with deterministic concurrency tests, oracle, licensing,
and sanitizer behavior. External material is useful for private concept study
or source discovery only and needs explicit license and semantic-contamination
review.

The tasks below therefore materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## V2 Replacement Tasks

| ID | Primary state model | Distinguishing contract |
|---|---|---|
| `audio-spsc-frame-pipe` | SPSC slot cursors | Blocking full/empty coordination and drain-after-finish. |
| `camera-generation-overwrite` | Generation-stamped overwrite slots | Strict generations and exact skipped-frame reporting. |
| `telemetry-source-quota-ring` | Per-source subrings | Independent quotas and round-robin fairness. |
| `network-fragment-assembly-ring` | Packet assembly slots | Out-of-order fragments become visible only as complete packets. |
| `log-severity-lane-ring` | Three severity rings | Fixed 2:1:1 weighted service cycle. |
| `keyboard-transition-coalescer` | Key-indexed tombstone slots | Inverse transitions cancel while unrelated order survives. |
| `can-sequence-reorder-window` | Sequence-indexed modular window | Only the exact next sequence is consumable. |
| `market-symbol-coalescing-ring` | Symbol-indexed circular slots | Pending updates replace in place without moving symbol order. |
| `gps-watermark-batch-ring` | Watermark-released sample slots | Ready batches sort by timestamp then admission. |
| `build-epoch-barrier-ring` | Epoch worker bitmaps | Only a complete current epoch becomes visible. |
| `video-reservation-commit-ring` | Generation-stamped slot states | Reserve, commit, cancel, and head visibility are separate transitions. |
| `sensor-timestamp-merge-ring` | Per-source rings plus watermarks | A safe k-way minimum requires every source watermark. |
| `print-aging-priority-ring` | Age-promoted priority slots | Promotion and priority/age tie rules replace FIFO. |
| `payment-hash-chain-ring` | Digest-linked circular slots | Invalid predecessor/digest links never mutate the chain. |
| `file-change-debounce-ring` | Path-indexed change algebra | Create/modify/delete transitions reduce or cancel pending work. |
| `robot-command-retry-ring` | Queue plus one in-flight state | Ack/nack controls retry rotation and terminal removal. |
| `support-broadcast-cursor-ring` | Per-consumer sequence cursors | Slots reclaim only after every consumer advances. |
| `weather-aggregation-bucket-ring` | Stamped modular aggregates | Colliding ticks expire buckets; values aggregate rather than queue. |
| `game-tick-snapshot-ring` | Sealed tick/player maps | Per-player overwrite precedes ordered sealed snapshots. |
| `warehouse-dedup-window-ring` | Generation history plus scan slots | Duplicate suppression outlives queue consumption and expires by admission count. |

## Materialization Requirements

Every root needs a task-specific C++17 public API and a distinct primary state
model. Changing only nouns, method names, overflow policy, or one extension on
the same queue is a blocking duplicate-family failure. The reference, public
operations, invalid-state behavior, and private discriminator must all differ
materially. Generic `std::deque<int>`/queue-adaptor implementations are
forbidden as the substantive mechanism.

The contract must state whether a full ring blocks, rejects, drops newest,
drops oldest, or coalesces eligible entries. It must state whether consumers
drain accepted entries after closure and whether ordering is global or scoped
by producer/source. For each task, author a documented provenance record,
starter header/source pair, independent reference implementation, visible
examples, hidden tests, an executable independent-model trace, a task-specific
broken-reference fixture, a normal build, and a fresh locked sanitizer build.

The combined visible, hidden, and model tests must cover the operation classes
and edge cases that exist in that task's contract. They must not impose generic
queue behavior on roots whose primary mechanism is aggregation, coalescing,
barriers, retries, snapshots, or multi-consumer retention. Required evidence
includes:

- empty/full behavior and cursor or generation wraparound where applicable;
- the task's complete observable ordering, which may be FIFO, weighted,
  sequence-based, timestamp-based, priority-based, or snapshot-based;
- exactly the stated full-ring policy with no accidental loss or duplication;
- close while producers and consumers are blocked, including draining accepted
  entries before terminal consumer completion;
- producer/consumer cardinality promised by the task contract;
- source/sequence ordering and coalescing behavior where applicable;
- ring counters, dropped-event diagnostics, and snapshot behavior where exposed;
- deterministic concurrency coordination using barriers, promises, or explicit
  gates where the public contract exposes blocking—never timing sleeps;
- bounded sanitizer executions with explicit per-test timeouts;
- a deterministic stateful trace checked after every operation against an
  independent value/container model, including return values, complete
  observable contents/order, and every public operation class;
- a task-specific negative implementation that compiles successfully and is
  rejected by executing hidden/model tests. Grepping the good reference or
  accepting compile failure is not negative-fixture evidence.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
