# Circular Buffer Curriculum: Topic 1, Circular Buffers

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum teaches fixed-capacity FIFO state management: read/write
cursors, size accounting, full-versus-empty distinction, wraparound, and
explicit overwrite behavior. The official Aider Polyglot C++ `circular-buffer`
task is a permanent benchmark holdout. Do not copy it, its tests, its
reference, its prompts, or close semantic variants into SFT data.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

Circular-buffer exercises and implementations are widely available online.
They are useful for private concept study or source discovery only. They are
not a drop-in SFT source inventory: every external source needs explicit
license and semantic-contamination review, and direct ring-buffer exercises
are benchmark-adjacent.

The tasks below therefore materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `ring-telemetry-history` | Telemetry history | Record sensor samples, take ordered snapshots, and optionally overwrite oldest samples. |
| `ring-audio-frame-store` | Audio frame store | Queue audio frames, reject overflow, and drain frames in playback order. |
| `ring-camera-preview` | Camera preview | Keep the most recent preview frames, dropping the oldest frame on forced capture. |
| `ring-gps-trail` | GPS trail | Retain a bounded route history and expose oldest/newest coordinates. |
| `ring-ui-event-queue` | UI event queue | Enqueue, dispatch, and coalesce bounded user-interface events. |
| `ring-keyboard-input` | Keyboard input | Buffer keystrokes, consume batches, and report dropped input on overflow. |
| `ring-network-packets` | Network packet queue | Receive packets, reject full-buffer arrivals, and read packet metadata FIFO. |
| `ring-stock-ticks` | Stock tick window | Store a recent price window and replace the oldest tick when capacity is reached. |
| `ring-workout-laps` | Workout laps | Add lap records, undo the newest lap, and enumerate retained laps in chronological order. |
| `ring-print-spool` | Print spool | Accept jobs until full, cancel a queued job by ID, and dispatch the oldest job. |
| `ring-game-replay` | Game replay | Maintain a fixed replay-event tail and seek by offset from oldest or newest. |
| `ring-machine-alerts` | Machine alerts | Record alerts, acknowledge the oldest alert, and force-record critical alerts. |
| `ring-log-tail` | Log tail | Append log lines, clear the tail, and export the retained suffix in insertion order. |
| `ring-currency-quotes` | Currency quotes | Keep a bounded quote stream and return the newest N observations. |
| `ring-medication-reminders` | Medication reminders | Queue reminders, mark delivery, and overwrite stale reminders under a policy flag. |
| `ring-customer-arrivals` | Customer arrivals | Record arrivals, serve the next customer, and report current queue depth. |
| `ring-bus-messages` | Bus-message buffer | Store fixed-size controller messages and distinguish rejected from overwritten sends. |
| `ring-build-events` | Build-event buffer | Retain recent compiler events and drain all events after a sequence cursor. |
| `ring-weather-readings` | Weather readings | Maintain a rolling environmental window and calculate a summary over retained samples. |
| `ring-delivery-scans` | Delivery scans | Add parcel scans, pop oldest scans, and inspect wraparound-safe chronological snapshots. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a textbook
`read()` / `write()` circular-buffer API as the visible assignment. The
overflow policy, batch behavior, eviction semantics, cancellation behavior,
snapshot/query behavior, and invalid-input rules must materially differ
between roots.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- zero, one, and larger capacities under the task-specific capacity policy;
- empty-buffer reads and full-buffer writes;
- wraparound after one and many enqueue/dequeue cycles;
- FIFO order across the physical end of the backing storage;
- exactly one size/cursor transition for forced overwrite of the oldest item;
- rejection without state mutation for non-overwriting full-buffer writes;
- clear, batch drain, cancellation, or resize behavior where applicable;
- repeated snapshots that do not mutate the buffer;
- long randomized operation sequences checked against a `std::deque` oracle.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A task judged to be a
close semantic copy of the official benchmark `circular-buffer` root must be
rejected from SFT and may only be retained as a separate internal diagnostic
candidate where permitted.
