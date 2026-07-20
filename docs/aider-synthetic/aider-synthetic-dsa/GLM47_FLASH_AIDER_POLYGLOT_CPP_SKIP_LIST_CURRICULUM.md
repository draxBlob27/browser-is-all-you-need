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
- `docs/AIDER_SFT_SCOPE.md`

## Online Material Status

Skip-list explanations and exercises exist online, especially in Open Data
Structures. They are useful for private concept study or source discovery only.
They do not provide a ready 20-task C++ SFT corpus: every external source
needs explicit license and semantic-contamination review.

The tasks below therefore materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, random-level policy, and
provenance must be created in-repo and pass the normal original-task admission
process.

## Legacy Audit And V2 Direction

The first materialization implemented one generic CRUD/rank/page skip list 20
times under renamed domain APIs. It remains preserved under
`.w8-biayn/data/aider-tasks/aider-dsa/skip-list/` as audit input. The v2
re-verification replaces that template family with the 20 mechanism-specific
roots defined in `docs/aider-tasks-spec/aider-dsa/skip-list.md` and writes only
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/skip-list/`.

The v2 inventory covers descending price towers, indexed widths, counted
multiplicity, interval augmentation, finger search, circular successor,
deterministic and explicit tower heights, bidirectional links, unrolled
blocks, tombstones and compaction, version snapshots, lexicographic prefixes,
coupled indexes, weighted spans, disjoint extents, expiry buckets, first-fit
gaps, floor thresholds, and tower merging. These are planning roots, not a
release quota or dataset admission.

## Legacy Proposed Tasks

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

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Local remediation ends at `local_family_verified` after owner regeneration,
prompt/role checks, mandatory network-disabled Docker normal and fresh
ASan/UBSan reference evidence, negative-fixture execution, and family plus
benchmark screening. Any future dataset intake requires a separately
authorized contract.

## Local Re-verification Status

The first v2 completion claim was withdrawn because its synthetic clone
controls bypassed the production pair evaluator and its marker-only negative
sources failed at CMake configure without executing tests. V3 reopens all 20
remedies. It derives seven hard-rule dimensions from emitted artifacts, routes
all 190 pairs plus the required emitted-artifact adversarial clones through one
production evaluator, and generates one complete compiling topic-specific
false source per root. `local_family_verified` may be restored only after the
pinned, network-disabled Docker run passes 40 normal and 40 fresh ASan/UBSan
tests and all 20 false sources discover and execute the same tests before being
rejected. Those v3 gates have now passed and the family is
`local_family_verified`. Exact dispositions, findings, hashes, and receipt locations are
recorded in `docs/aider-tasks-spec/aider-dsa/skip-list.md`. This remains local
task evidence only; it is not dataset release, export, or training readiness.
