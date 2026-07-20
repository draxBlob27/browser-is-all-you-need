# Threaded Binary Tree Curriculum: Topic 1, Subtask 6

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This is the sixth subtask under **Linked Structure Invariants**. Its purpose is
to teach the distinction between child edges and inorder predecessor/successor
threads, together with safe mutation and traversal, through C++17 tasks with
domain-specific APIs.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

## Online Material Status

Threaded-binary-tree explanations and isolated exercises are available online,
but there is no ready 20-task C++ corpus with consistent starter code, oracle,
and licensing. External material is useful for private concept study or source
discovery only and needs explicit license and semantic-contamination review.

The tasks below therefore materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, thread-marker representation,
and provenance must be created in-repo and pass the normal original-task
admission process.

## Remediated v2 Tasks

The legacy 20-root noun-renamed template remains immutable audit input. The v2
family keeps one independently justified representative and replaces the other
19 roots with the algorithmically distinct inventory in
`docs/aider-tasks-spec/aider-dsa/threaded-binary-tree.md`. The owner emits that
one-to-one disposition map only under the parallel re-verification root; no
rename-only legacy task is retained.

| ID | Task | Visible contract |
|---|---|---|
| `threaded-calendar-navigator` | Calendar navigator | Add or cancel event keys and move to the previous or next event without rebuilding an ordered list. |
| `threaded-library-shelves` | Library shelves | Register call numbers and navigate shelf neighbors in sorted order. |
| `threaded-audit-browser` | Audit browser | Insert, redact, and step through ordered audit records in both directions. |
| `threaded-flight-departures` | Flight departures | Maintain departure keys and find immediate neighboring departures. |
| `threaded-sensor-thresholds` | Sensor thresholds | Add or remove thresholds and navigate floor or ceiling boundaries. |
| `threaded-file-version-browser` | File-version browser | Store revisions and move forward or backward through retained versions. |
| `threaded-parking-space-guide` | Parking-space guide | Reserve or release spaces and walk to adjacent occupied or available IDs. |
| `threaded-museum-waypoints` | Museum waypoints | Add or remove numbered exhibits and traverse the tour in either direction. |
| `threaded-score-history` | Score history | Insert score events and navigate chronological predecessor or successor entries. |
| `threaded-medication-times` | Medication times | Schedule or cancel doses and find the next or previous dose. |
| `threaded-cargo-manifest` | Cargo manifest | Index cargo IDs and iterate a selected ID interval forward or backward. |
| `threaded-route-stations` | Route stations | Insert or close stations and step through adjacent stations by route code. |
| `threaded-ticket-browser` | Ticket browser | Open or resolve ticket numbers and page through unresolved tickets. |
| `threaded-fare-tiers` | Fare tiers | Maintain fare thresholds and navigate nearest cheaper or more-expensive tiers. |
| `threaded-appointment-book` | Appointment book | Reserve or release times and enumerate a bounded time interval in both directions. |
| `threaded-inventory-catalog` | Inventory catalog | Add or discontinue SKU keys and find neighboring catalog entries. |
| `threaded-document-anchors` | Document anchors | Store anchors and navigate the closest predecessor or successor anchor. |
| `threaded-auction-bids` | Auction bids | Insert or withdraw bid levels and step across sorted price levels. |
| `threaded-network-ports` | Network ports | Reserve or free ports and traverse the neighboring reserved ports. |
| `threaded-transit-service` | Transit service | Add or cancel services and page departures around a time cursor. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a textbook
tree-node API as the visible assignment. The observable operations,
duplicate/invalid-input policy, forward/backward navigation semantics, and
edge cases must materially differ between roots.

The scaffold must make a child edge distinguishable from an inorder thread,
for example through explicit `is_left_thread` and `is_right_thread` markers.
For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- empty and singleton structures;
- leftmost and rightmost nodes with null predecessor/successor threads;
- every combination of real child edge and predecessor/successor thread;
- forward inorder traversal and reverse inorder traversal agreement;
- insertion at the ordered extremes and between existing keys;
- deletion of leaves, one-child nodes, two-child nodes, and the root while
  repairing adjacent threads;
- duplicate-key and invalid-navigation behavior under the task contract;
- long randomized mutation sequences checked against a sorted-vector or
  ordered-map oracle.

For v2, the common representation is a heap-owned ordered binary tree whose
markers distinguish real children from inorder predecessor/successor threads.
Shared direct insertion/deletion is the structural substrate; each task must
also implement its root-specific multiplicity, tombstone, cursor, interval,
rank, aggregate, payload, balanced-build, range-prune, split, gap, state,
rekey, audit, hysteresis, composite-order, or wrap algorithm. The v3 family
screen derives evidence from actual emitted artifacts and requires every one
of the 190 unordered pairs to differ in public API, owned state or algorithm,
mutation/selection rules, invalid/boundary behavior, reference control flow,
deterministic oracle, and topic-specific negative fixture. Focused tests must
inject domain/identifier-renamed, constants-or-policy-only, and
opposite-end-selection clones into the real rejecting screen. Each counted
root's private false implementation must compile with the ordinary strict
flags and then be rejected by the same executed visible/private tests. The
earlier v2 aggregate-similarity and shared-fixture claim is withdrawn.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
