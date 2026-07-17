# Bounded Blocking Queue Curriculum: Topic 1, Bounded Blocking Queues

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum teaches the bounded FIFO state machine plus synchronization:
capacity, full/empty blocking, wakeups, closure, and producer/consumer
ownership. Tasks use C++17 mutexes and condition variables with deterministic
test coordination.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

Bounded-blocking-queue examples and concurrency tutorials are available online,
but there is no ready 20-task C++ corpus with consistent deterministic tests,
oracle, licensing, and sanitizer behavior. External material is useful for
private concept study or source discovery only and needs explicit license and
semantic-contamination review.

The tasks below therefore materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `bbq-print-dispatch` | Print dispatcher | Producers submit print jobs; workers take jobs until the dispatcher closes. |
| `bbq-image-upload` | Image upload pipeline | Bounded upload requests block producers when workers fall behind. |
| `bbq-telemetry-ingest` | Telemetry ingest | Sensors submit readings; a consumer drains ordered batches and closes cleanly. |
| `bbq-audio-processing` | Audio processor | Audio frames are produced and consumed FIFO with explicit end-of-stream. |
| `bbq-log-writer` | Log writer | Application threads enqueue log records; a writer drains all records before shutdown. |
| `bbq-order-kitchen` | Kitchen order queue | Waitstaff submit orders; cooks take orders and receive closure after service. |
| `bbq-build-worker-pool` | Build worker pool | Build requests block at capacity and workers stop only after queued work drains. |
| `bbq-email-delivery` | Email delivery queue | Send requests are queued, cancelled before dispatch, and drained on close. |
| `bbq-document-indexer` | Document indexer | Producers add document IDs; indexers consume work with bounded backpressure. |
| `bbq-network-message-pump` | Network message pump | Inbound messages wait for capacity and consumers observe FIFO delivery. |
| `bbq-customer-support` | Support ticket intake | Ticket producers block under load; agents take tickets until intake closes. |
| `bbq-sensor-fusion` | Sensor fusion queue | Multiple sensor streams enqueue samples; fusion consumes a finite ordered stream. |
| `bbq-video-transcode` | Video transcode queue | Upload workers submit segments and transcoders drain segments before final close. |
| `bbq-payment-retry` | Payment retry queue | Retry requests are produced, taken once, and rejected after the queue closes. |
| `bbq-route-calculation` | Route calculation queue | Requesters submit route jobs; workers consume jobs and report pending count safely. |
| `bbq-database-write-behind` | Write-behind queue | Callers enqueue mutations; a writer flushes all queued mutations before stopping. |
| `bbq-notification-delivery` | Notification delivery queue | Multiple producers enqueue notifications and a dispatcher waits safely for work. |
| `bbq-file-scan` | File scan queue | Directory-walk producers submit paths; scan workers exit only after completion closure. |
| `bbq-fraud-review` | Fraud review queue | Review jobs obey capacity, support graceful close, and expose queue statistics. |
| `bbq-warehouse-pick` | Warehouse pick queue | Pick requests are queued FIFO and workers receive a closed-and-drained result. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose only a
textbook `push` / `pop` queue assignment. Closure behavior, cancellation,
batching, error result, statistics, and producer/consumer lifecycle semantics
must materially differ between roots.

The implementation contract must define whether a blocked producer is released
with failure or an exception after closure, whether consumers drain pre-close
items, and whether cancellation preserves FIFO order among remaining items.
For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- FIFO ordering with one producer and one consumer;
- full-queue producer blocking and empty-queue consumer blocking;
- wakeup after dequeue and wakeup after enqueue;
- close while producers or consumers are blocked;
- draining all items queued before close before consumers report completion;
- capacity one, larger capacity, and closure of an empty queue;
- multiple producers and consumers without loss, duplication, or data races;
- cancellation or statistics behavior where the task exposes it;
- a deterministic coordination harness using barriers, promises, or explicit
  test gates—never `sleep_for` timing assumptions;
- sanitizer-enabled stress iterations with bounded joins and clear failure
  diagnostics.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
