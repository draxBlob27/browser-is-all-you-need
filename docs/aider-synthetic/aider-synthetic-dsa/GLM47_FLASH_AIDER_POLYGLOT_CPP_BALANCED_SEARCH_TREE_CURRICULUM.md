# Balanced Search Tree Curriculum: Topic 1, Subtask 3

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This is the third subtask under **Linked Structure Invariants**: AVL and
red-black trees. The official Aider Polyglot C++ `binary-search-tree` task is
a permanent benchmark holdout. Do not copy it, its tests, its reference, its
prompts, or close semantic variants into SFT data.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

AVL and red-black tree references and exercises are available online, notably
in Open Data Structures and competitive-programming resources. They are useful
for private concept study or source discovery only. They are not a drop-in SFT
source inventory: every external source needs explicit license and semantic
contamination review, and direct balanced-BST exercises are benchmark-adjacent.

The tasks below therefore materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Original Tasks

| ID | Tree | Task | Visible contract |
|---|---|---|---|
| `avl-live-leaderboard` | AVL | Live leaderboard | Insert, update, and remove scores while returning rank-adjacent entries. |
| `avl-api-rate-limits` | AVL | API rate limits | Add or expire timestamped limits and query the nearest active thresholds. |
| `avl-appointment-slots` | AVL | Appointment slots | Reserve or cancel slots and find the nearest available slot. |
| `avl-inventory-restock` | AVL | Inventory restock | Maintain reorder levels and query the closest level meeting a demand. |
| `avl-memory-free-ranges` | AVL | Memory free ranges | Split, merge, allocate, and release ordered free blocks. |
| `avl-coupon-thresholds` | AVL | Coupon thresholds | Add or retire spending thresholds and resolve the best applicable rule. |
| `avl-game-matchmaking` | AVL | Game matchmaking | Join or leave ratings and find the closest compatible opponent. |
| `avl-energy-tariffs` | AVL | Energy tariffs | Update tariff breakpoints and resolve the active tariff for usage. |
| `avl-shipping-weight-bands` | AVL | Shipping weight bands | Maintain bands and find the next valid weight boundary. |
| `avl-library-holds` | AVL | Library holds | Insert or cancel hold priorities and return the next eligible request. |
| `rb-order-book` | Red-black | Order book | Add, cancel, and replace bid levels while finding the best bid or ask. |
| `rb-file-version-index` | Red-black | File-version index | Store revisions, erase versions, and resolve floor or ceiling revisions. |
| `rb-reservation-directory` | Red-black | Reservation directory | Allocate or release confirmation codes and find neighboring bookings. |
| `rb-medication-schedule` | Red-black | Medication schedule | Insert or cancel dose times and find the previous or next dose. |
| `rb-access-control-rules` | Red-black | Access-control rules | Add or revoke numeric rule IDs and resolve the highest matching rule. |
| `rb-cargo-manifest` | Red-black | Cargo manifest | Add, amend, or remove cargo IDs and query bounded ID ranges. |
| `rb-metric-percentiles` | Red-black | Metric percentiles | Maintain unique observations and resolve percentile boundary values. |
| `rb-travel-fare-table` | Red-black | Travel fare table | Insert or remove fare tiers and find the best fare not exceeding a budget. |
| `rb-audit-event-index` | Red-black | Audit-event index | Insert, redact, and range-query ordered audit events. |
| `rb-support-escalations` | Red-black | Support escalations | Track escalation priorities, alter priority, and fetch the next case. |

## Materialization Requirements

Every root needs a task-specific C++17 public API; do not expose generic tree
nodes or ask learners to implement a textbook `insert` method. The externally
observable operation sequence, invalid-input behavior, duplicate policy, and
aggregate/query semantics must materially differ between roots.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- the four AVL rotation shapes: LL, RR, LR, and RL;
- AVL deletion rebalancing and height consistency;
- red-black root-black, no-red-red-parent-child, and equal-black-height
  invariants;
- leaf, one-child, two-child, and root deletion;
- duplicate and empty/singleton behavior under the task-specific contract;
- floor, ceiling, predecessor, successor, rank, or range boundaries where
  applicable;
- long randomized mutation sequences checked against a sorted-vector or
  ordered-map oracle.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A task judged to be a
close semantic copy of the official benchmark `binary-search-tree` root must
be rejected from SFT and may only be retained as a separate internal diagnostic
candidate where permitted.

## Local Materialization

All 20 proposed roots are implemented by
`w8_biayn.integrations.moonlight_balanced_search_tree_aider_tasks`.
Materialize and verify them with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_balanced_tree_aider_tasks.sh --verify
```

The command creates only `.w8-biayn/data/aider-tasks/aider-dsa/balanced-search-tree/`.
It does not admit, split, export, or claim a primary SFT dataset release.
