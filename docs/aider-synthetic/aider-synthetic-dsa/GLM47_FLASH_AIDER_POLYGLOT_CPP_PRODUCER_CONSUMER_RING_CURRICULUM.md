# Producer-Consumer Ring Curriculum: Topic 1, Producer-Consumer Rings

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

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
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

Producer-consumer ring examples are available online, but there is no ready
20-task C++ corpus with deterministic concurrency tests, oracle, licensing,
and sanitizer behavior. External material is useful for private concept study
or source discovery only and needs explicit license and semantic-contamination
review.

The tasks below therefore materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `pcr-audio-capture` | Audio capture ring | Capture frames from one producer and deliver them FIFO to one playback consumer. |
| `pcr-camera-frames` | Camera frame ring | Capture bounded frames and drop the oldest frame under an explicit overload policy. |
| `pcr-telemetry-uplink` | Telemetry uplink ring | Sensor producers submit readings; an uplink worker drains them before close. |
| `pcr-network-receiver` | Network receiver ring | Receive packets with backpressure and deliver packets once to consumer workers. |
| `pcr-log-ingest` | Log-ingest ring | Application producers write records; a logger consumes all pre-close records. |
| `pcr-keyboard-events` | Keyboard event ring | Input producer emits events; UI consumer drains events with explicit overflow reporting. |
| `pcr-can-bus` | CAN-bus ring | Controller messages enter a bounded ring and are consumed in sequence-number order. |
| `pcr-market-ticks` | Market-tick ring | Feed ticks into a bounded stream that coalesces only same-symbol pending updates. |
| `pcr-gps-samples` | GPS-sample ring | A location producer publishes samples; consumer obtains chronological batches. |
| `pcr-build-events` | Build-event ring | Parallel compiler workers submit events and one reporter drains a closed ring. |
| `pcr-video-segments` | Video-segment ring | Encoder producers place segments; upload consumer observes FIFO segment IDs. |
| `pcr-sensor-fusion` | Sensor-fusion ring | Multiple sources publish tagged samples and a fusion worker drains each exactly once. |
| `pcr-print-pipeline` | Print pipeline ring | Producers enqueue print payloads; printer consumes until a graceful shutdown. |
| `pcr-payment-events` | Payment-event ring | Payment workers publish immutable events and an auditor consumes an ordered stream. |
| `pcr-file-watch` | File-watch ring | Watcher producer publishes filesystem changes; indexer consumes batched changes. |
| `pcr-robot-commands` | Robot-command ring | Planner publishes commands; controller takes commands with explicit full-ring policy. |
| `pcr-support-notifications` | Support-notification ring | Ticket updates enter a ring and dispatcher workers deliver every accepted update once. |
| `pcr-weather-station` | Weather-station ring | Station samples flow to an aggregator that tracks dropped or overwritten samples. |
| `pcr-game-input` | Game-input ring | Input events are produced and consumed per simulation tick with bounded backlog behavior. |
| `pcr-warehouse-scans` | Warehouse-scan ring | Scanner threads submit parcel events; one inventory consumer drains and closes cleanly. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a generic
ring `enqueue`/`dequeue` implementation as the visible assignment. The
producer/consumer cardinality, overflow policy, batching, coalescing,
statistics, sequencing, and closure behavior must materially differ between
roots.

The contract must state whether a full ring blocks, rejects, drops newest,
drops oldest, or coalesces eligible entries. It must state whether consumers
drain accepted entries after closure and whether ordering is global or scoped
by producer/source. For each task, author a documented provenance record,
starter header/source pair, independent reference implementation, visible
examples, hidden Catch tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- empty and full ring behavior, capacity one, and cursor wraparound;
- FIFO delivery for accepted entries across many wraparound cycles;
- exactly the stated full-ring policy with no accidental loss or duplication;
- close while producers and consumers are blocked, including draining accepted
  entries before terminal consumer completion;
- producer/consumer cardinality promised by the task contract;
- source/sequence ordering and coalescing behavior where applicable;
- ring counters, dropped-event diagnostics, and snapshot behavior where exposed;
- deterministic concurrency coordination using barriers, promises, or explicit
  gates—never timing sleeps;
- bounded stress runs under sanitizer with joins that cannot hang silently;
- randomized operation traces checked against a synchronized deque/reference
  model with the same declared overflow policy.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
