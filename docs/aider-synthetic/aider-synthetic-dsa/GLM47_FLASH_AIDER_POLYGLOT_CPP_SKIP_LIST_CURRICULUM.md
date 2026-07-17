# Skip List Curriculum: Topic 1, Subtask 5

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This is the fifth subtask under **Linked Structure Invariants**. Its purpose is
to teach multi-level forward-link consistency, ordered mutation, rank/index
accounting, and safe probabilistic balancing through C++17 tasks with
domain-specific APIs.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

Skip-list explanations and exercises exist online, especially in Open Data
Structures. They are useful for private concept study or source discovery only.
They do not provide a ready 20-task C++ SFT corpus: every external source
needs explicit license and semantic-contamination review.

The tasks below therefore materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, random-level policy, and
provenance must be created in-repo and pass the normal original-task admission
process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `skip-live-leaderboard` | Live leaderboard | Insert, update, erase, rank, and paginate uniquely ranked players. |
| `skip-event-timeline` | Event timeline | Add or retract timestamped events and seek by timestamp or ordinal position. |
| `skip-percentile-meter` | Percentile meter | Maintain observations and return rank, quantile, floor, and ceiling values. |
| `skip-log-retention` | Log retention | Insert log sequence IDs, expire a range, and page forward from a cursor. |
| `skip-route-markers` | Route markers | Add, remove, and find neighboring distance markers on a route. |
| `skip-cargo-priorities` | Cargo priorities | Maintain cargo priority keys and retrieve a bounded priority slice. |
| `skip-reservation-waitlist` | Reservation waitlist | Join, cancel, reprioritize, and select the nth waitlisted reservation. |
| `skip-notebook-lines` | Notebook lines | Insert or delete numbered lines and retrieve by ordinal line number. |
| `skip-student-ranks` | Student ranks | Update scores and return student rank plus nearby ranked students. |
| `skip-search-result-pages` | Search-result pages | Store result IDs by score and return deterministic cursor pages. |
| `skip-metric-window` | Metric window | Add samples, evict an ID range, and query median or rank interval. |
| `skip-file-offset-index` | File-offset index | Insert or remove file blocks and find the block at or before an offset. |
| `skip-order-statistics` | Order statistics | Maintain a multiset-like collection with explicit count and kth-value queries. |
| `skip-feature-rollout` | Feature rollout | Add or retire rollout thresholds and resolve the active threshold for a user bucket. |
| `skip-expiring-cache-index` | Expiring-cache index | Register expiry timestamps, invalidate expired keys, and query the next expiry. |
| `skip-auction-price-levels` | Auction price levels | Add, amend, cancel, and enumerate price levels in a requested range. |
| `skip-calendar-slots` | Calendar slots | Reserve or cancel slots and select the kth available slot after a time. |
| `skip-inventory-reorder` | Inventory reorder | Track reorder points and retrieve the next N affected stock levels. |
| `skip-document-anchors` | Document anchors | Insert or remove anchors and resolve the nearest anchor before a position. |
| `skip-transit-departures` | Transit departures | Insert, cancel, and page scheduled departures from a time cursor. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a textbook
`SkipList` class as the assignment. The observable operations, duplicate
policy, cursor/rank behavior, invalid-input behavior, and ordering semantics
must materially differ between roots.

The task framework must inject or seed the level-selection policy so tests are
reproducible. Randomness must not make correct implementations flaky. For each
task, author a documented provenance record, starter header/source pair,
independent reference implementation, visible examples, hidden Catch tests,
normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- ordered level-zero traversal and complete membership of every higher level;
- sorted forward links at every level;
- insertion and deletion of values promoted to multiple levels;
- removal of an element that is the only member of a high level;
- head/tail, empty, singleton, duplicate, and adjacent-key behavior;
- rank, select, cursor, and range boundary behavior where applicable;
- deterministic ties and stable pagination under the task contract;
- long seeded mutation sequences checked against a sorted-vector or
  ordered-map oracle.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
