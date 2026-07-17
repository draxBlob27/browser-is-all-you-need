# Circular Deque Curriculum: Topic 1, Circular Deques

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum teaches bounded double-ended state management: front and back
cursors, full-versus-empty distinction, wraparound at both ends, and explicit
overflow/underflow policies. The official Aider Polyglot C++ `circular-buffer`
task is a permanent benchmark holdout. Do not copy it, its tests, its
reference, its prompts, or close semantic variants into SFT data.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

Circular-deque exercises and implementations are available online, but they
are useful for private concept study or source discovery only. They are not a
drop-in SFT source inventory: every external source needs explicit license and
semantic-contamination review, and bounded-ring exercises are benchmark-adjacent.

The tasks below therefore materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `cdeque-shuttle-stops` | Shuttle stops | Add urgent stops at the front, regular stops at the back, and serve from either end. |
| `cdeque-patient-triage` | Patient triage | Admit routine or emergency patients at different ends and select the next patient by policy. |
| `cdeque-card-draw-pile` | Card draw pile | Draw from either end, return cards to selected ends, and reject over-capacity returns. |
| `cdeque-audio-jitter` | Audio jitter buffer | Insert late frames at the front or normal frames at the back and drain playback frames. |
| `cdeque-delivery-resequence` | Delivery resequencer | Add expedited parcels at the front, standard parcels at the back, and dispatch by side. |
| `cdeque-browser-tabs` | Browser tab deque | Open foreground/background tabs at opposite ends and close either end. |
| `cdeque-print-priority` | Print priority queue | Submit urgent and normal jobs to different ends and dispatch selected ends. |
| `cdeque-event-replay` | Event replay | Append events, prepend recovered events, and replay forward or backward. |
| `cdeque-ticket-escalation` | Ticket escalation | Escalate tickets to the front, demote to the back, and resolve from policy-selected ends. |
| `cdeque-warehouse-loading` | Warehouse loading lane | Load fragile and standard packages from opposite ends and unload by dock direction. |
| `cdeque-game-turns` | Game turns | Insert bonus turns at the front, normal turns at the back, and rotate active turns. |
| `cdeque-transit-passengers` | Transit passenger queue | Board priority passengers at the front, regular passengers at the back, and unload at either door. |
| `cdeque-log-recovery` | Log recovery | Prepend recovered records, append live records, and consume oldest/newest records. |
| `cdeque-tool-rental` | Tool rental queue | Return urgent repair tools to the front, normal returns to the back, and issue from either end. |
| `cdeque-sensor-calibration` | Sensor calibration queue | Add high-priority calibrations at the front and routine jobs at the back. |
| `cdeque-meal-orders` | Meal order line | Add rush orders at the front, standard orders at the back, and serve kitchen-selected ends. |
| `cdeque-route-detours` | Route detours | Prepend temporary detours, append planned stops, and remove either next route action. |
| `cdeque-media-preview` | Media preview buffer | Add instant previews at the front, queued previews at the back, and discard from either side. |
| `cdeque-support-callbacks` | Support callbacks | Escalate callbacks to the front, queue routine callbacks at the back, and take by service mode. |
| `cdeque-build-work-items` | Build work items | Add retry work at the front, new work at the back, and process from an explicitly chosen side. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose only generic
`push_front`, `push_back`, `pop_front`, and `pop_back` operations as the visible
assignment. Side-selection policy, capacity behavior, batching, invalid-input
handling, and visible state/query semantics must materially differ between
roots.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- zero, one, and larger capacities under the task contract;
- empty deque removal from both sides and full deque insertion at both sides;
- front wraparound, back wraparound, and both occurring in one operation trace;
- alternating front/back insertion and removal while preserving logical order;
- exactly correct cursor/size behavior when a side-specific overwrite policy
  is part of the contract;
- no state mutation on rejected full/empty operations;
- snapshots and side-specific serving behavior without accidental reversal;
- long randomized mixed-end sequences checked against a `std::deque` oracle.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A task judged to be a
close semantic copy of the official benchmark `circular-buffer` root must be
rejected from SFT and may only be retained as a separate internal diagnostic
candidate where permitted.
