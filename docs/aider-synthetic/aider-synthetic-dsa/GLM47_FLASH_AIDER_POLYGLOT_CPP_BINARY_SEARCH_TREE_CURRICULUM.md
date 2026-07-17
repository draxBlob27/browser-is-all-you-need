# Binary Search Tree Curriculum: Topic 1, Subtask 2

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This is the second subtask under **Linked Structure Invariants**. Its purpose
is to teach ordered pointer-structure invariants through C++17 tasks with
domain-specific contracts. The official Aider Polyglot C++
`binary-search-tree` task is a permanent benchmark holdout. Do not copy it,
its tests, its reference, its prompts, or close semantic variants into SFT
data.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

BST exercises are widely available online, including the C++ material in Open
Data Structures, Library Checker tasks, and online-judge tree problems. Those
resources are useful for private concept study or source discovery only. They
are not a drop-in SFT source inventory: every external source needs explicit
license and semantic-contamination review, and direct BST exercises are
benchmark-adjacent.

The tasks below therefore materialize as newly authored roots. Their required
behavior, C++ interface, tests, reference implementations, and provenance are
created in-repo and then pass the normal original-task admission process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `bst-appointment-index` | Appointment index | Add appointments by start time and find previous or next appointments. |
| `bst-price-book` | Price book | Maintain price levels and query the best price at or below a budget. |
| `bst-library-catalog` | Library catalog | Index unique call numbers and find neighboring shelf entries. |
| `bst-sensor-thresholds` | Sensor thresholds | Record thresholds and return closest lower and upper safety limits. |
| `bst-transit-departures` | Transit departures | Insert departure times and find the next available service. |
| `bst-warehouse-bins` | Warehouse bins | Allocate bin IDs and find predecessor or successor vacant bins. |
| `bst-access-key-registry` | Access-key registry | Register or revoke numeric keys, reject duplicates, and test membership. |
| `bst-scoreboard-ranks` | Scoreboard ranks | Track unique scores and report rank-adjacent scores. |
| `bst-version-catalog` | Version catalog | Store release numbers and resolve the latest release not newer than a request. |
| `bst-delivery-zones` | Delivery zones | Find a zone boundary immediately below or above an address number. |
| `bst-audit-timeline` | Audit timeline | Insert audit event IDs and retrieve a bounded chronological interval. |
| `bst-flight-standby` | Flight standby | Maintain priority numbers and promote the smallest eligible passenger. |
| `bst-energy-meter-readings` | Energy-meter readings | Insert readings and calculate count or sum within an inclusive range. |
| `bst-cargo-weight-index` | Cargo-weight index | Insert package weights and find the nearest allowed load weight. |
| `bst-auction-bids` | Auction bids | Add or retract bids and find the highest bid below a reserve. |
| `bst-parking-space-index` | Parking-space index | Allocate or release numbered spaces and find the nearest free space. |
| `bst-exam-score-index` | Exam-score index | Track scores and query percentile boundaries under a defined duplicate policy. |
| `bst-network-port-registry` | Network-port registry | Reserve or release ports and locate the next available port in a range. |
| `bst-document-revision-index` | Document-revision index | Insert revision IDs, erase a revision, and preserve ordered navigation. |
| `bst-ticket-number-index` | Ticket-number index | Open or close ticket numbers and query the next unresolved ticket. |

## Materialization Requirements

Every candidate must have a distinct C++17 public API. For example, expose
`next_departure_after(Time)` or `highest_bid_below(Money)` rather than generic
tree-node insertion or traversal functions. Domain renaming alone is not
enough: observable operations, invalid-input behavior, aggregate semantics,
and edge cases must materially differ between roots.

For each candidate, author:

1. a documented source/provenance record and task specification;
2. a starter header/source pair with the task-specific public API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. a normal build plus a fresh locked sanitizer build.

Hidden tests must exercise ordered-tree failures:

- empty and singleton structures;
- duplicate insertion and the task-specific duplicate policy;
- predecessor, successor, floor, and ceiling boundaries;
- deletion of leaves, one-child nodes, two-child nodes, and the root;
- inclusive and exclusive range boundaries where relevant;
- repeated insert/delete operations and retained aggregate correctness;
- sorted inorder traversal and BST ordering invariants;
- randomized operation sequences checked against a simple sorted-vector or
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
`w8_biayn.integrations.moonlight_binary_search_tree_aider_tasks`. Materialize
and verify them with:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_bst_aider_tasks.sh --verify
```

The command creates only `.w8-biayn/data/aider-tasks/aider-dsa/binary-search-tree/`; it
does not admit, split, export, or claim a primary SFT dataset release.
