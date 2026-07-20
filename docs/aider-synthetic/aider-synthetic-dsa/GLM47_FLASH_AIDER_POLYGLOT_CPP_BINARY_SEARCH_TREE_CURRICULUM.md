# Binary Search Tree Curriculum: Topic 1, Subtask 2

Status: `local_family_verified` in the locked network-disabled C++ image. The
20 roots are local diagnostic artifacts, not a dataset artifact.

The normative implementation contract is
`docs/aider-tasks-spec/aider-dsa/binary-search-tree.md`, SHA-256
`b374a2cff5d38009f1ccf7d5a54a504a24b97add40c1667603bac1f578ee55d5` at
this revision. If this curriculum and that specification disagree, the
specification controls.

## Purpose and Priority-1 learning objective

This is the second subtask under **Linked Structure Invariants**. Its primary
learning objective is not ordered-set behavior alone. Every retained task must
require a genuine, repository-owned, pointer-linked, unbalanced binary search
tree. The reference and applied solution must own nodes, traverse those nodes,
and perform insertion, lookup, predecessor/successor navigation, in-order
traversal, and leaf/one-child/two-child deletion on them.

`std::set`, maps, unordered containers, a sorted vector used as the index,
third-party trees, precomputed answers, hard-coded cases, or a dummy node tree
backed by another index do not achieve the objective. Incidental vectors for
returned results or a private behavior oracle, strings, optionals, and
`std::unique_ptr` ownership are allowed when they do not replace the BST.

A root remains `primary_core_objective: not_achieved` until source inspection
and a deterministic structural discriminator both prove the real tree. A
successful build, public examples, documentation, metadata, or behavioral
comparison against an ordered container cannot establish that result. This is
the first implementation and acceptance gate; all other work is secondary.

## Scope and permanent holdout

The official Aider Polyglot C++ `binary-search-tree` root is a permanent
benchmark holdout. Do not copy its wording, API, tests, reference,
implementation structure, or a close semantic variant. Online BST material,
including textbooks, Library Checker, and judge exercises, is for private
concept study or separately reviewed source discovery only. It is not a
drop-in source inventory.

Use this curriculum with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`;
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`;
- `docs/AIDER_SFT_SCOPE.md`;
- `docs/aider-tasks-spec/Original-specs.md`;
- `docs/aider-tasks-spec/verify-and-remedy.md`;
- `docs/aider-tasks-spec/aider-dsa/binary-search-tree.md`.

This is local clean-room task-family work. Optional dataset handoff is
`not_requested`.

## Current v1 audit and disposition

The current 20 roots under
`.w8-biayn/data/aider-tasks/aider-dsa/binary-search-tree/` exist and pass the
current focused generator test, but every reference delegates its substantive
state to `std::set<int>`. No reference contains a repository-owned BST node,
and current hidden tests use a set oracle without observing tree ownership,
ordering, shape, deletion, or augmentation. Therefore all 20 current roots
record `primary_core_objective: not_achieved` and disposition `replace`.

The replacements use new IDs and shared family ID
`aider-dsa-binary-search-tree-v2`; they must be materialized in the parallel
reverification root. Current roots are preserved as legacy evidence and must
not be overwritten, renamed, or called repaired.

| Current v1 root | Planned v2 replacement |
| --- | --- |
| `bst-access-key-registry` | `bst-access-key-leases-v2` |
| `bst-appointment-index` | `bst-appointment-reservations-v2` |
| `bst-auction-bids` | `bst-auction-order-book-v2` |
| `bst-audit-timeline` | `bst-audit-retention-log-v2` |
| `bst-cargo-weight-index` | `bst-cargo-load-classes-v2` |
| `bst-delivery-zones` | `bst-delivery-zone-rules-v2` |
| `bst-document-revision-index` | `bst-document-revision-ledger-v2` |
| `bst-energy-meter-readings` | `bst-energy-reading-ledger-v2` |
| `bst-exam-score-index` | `bst-exam-score-distribution-v2` |
| `bst-flight-standby` | `bst-flight-standby-queue-v2` |
| `bst-library-catalog` | `bst-library-shelf-records-v2` |
| `bst-network-port-registry` | `bst-network-port-leases-v2` |
| `bst-parking-space-index` | `bst-parking-free-intervals-v2` |
| `bst-price-book` | `bst-price-level-book-v2` |
| `bst-scoreboard-ranks` | `bst-scoreboard-player-ranks-v2` |
| `bst-sensor-thresholds` | `bst-sensor-hysteresis-rules-v2` |
| `bst-ticket-number-index` | `bst-ticket-priority-ledger-v2` |
| `bst-transit-departures` | `bst-transit-service-board-v2` |
| `bst-version-catalog` | `bst-semver-release-catalog-v2` |
| `bst-warehouse-bins` | `bst-warehouse-bin-inventory-v2` |

Current provenance establishes in-repository authoring but does not record a
license/usage decision, so every remedy begins `license_screen: pending`.
Resolve it before generation. A rejected license or provenance screen changes
the root to `reject` and stops; it is not deferred or waived.

## Planned v2 curriculum inventory

The 20 rows are a planning inventory, not a release quota and not evidence
that noun variants are independent training units. The normative specification
owns the complete C++17 declarations and behavior. Each row below names the
distinct state/query lesson and the extra structural discriminator beyond the
common BST invariant.

| Planned task | Domain capability | Distinct structural lesson |
| --- | --- | --- |
| `bst-access-key-leases-v2` | Grant/revoke keyed leases and query expiry windows. | Deletion preserves the complete owner/expiry payload. |
| `bst-appointment-reservations-v2` | Reserve nonoverlapping half-open appointments. | Subtree `max_end` remains exact through overlap search and successor deletion. |
| `bst-auction-order-book-v2` | Coalesce/cancel quantities and find the best price not above a limit. | Payload update occurs in-node; cancellation to zero deletes the node. |
| `bst-audit-retention-log-v2` | Retain events through an inclusive deadline and query predecessors. | Sequence traversal preserves retention equality and chronological ordering. |
| `bst-cargo-load-classes-v2` | Select the least maximum weight that accepts a load. | Lower-bound traversal returns the least qualifying key, including equality. |
| `bst-delivery-zone-rules-v2` | Store disjoint closed address ranges and locate a containing zone. | Exact subtree `max_end` distinguishes touching from overlapping ranges. |
| `bst-document-revision-ledger-v2` | Record/erase revisions and find the latest not after a request. | Predecessor search returns greatest key `<=` request, never a ceiling. |
| `bst-energy-reading-ledger-v2` | Count and sum readings in inclusive timestamp ranges. | Checked `subtree_sum` and size stay exact after mutation; overflow is atomic. |
| `bst-exam-score-distribution-v2` | Track duplicate scores and calculate a defined percentile. | Node multiplicity and occurrence-based subtree size drive order statistics. |
| `bst-flight-standby-queue-v2` | Promote the lowest eligible composite priority/sequence. | Composite-key deletion removes exactly one passenger without an auxiliary ID map. |
| `bst-library-shelf-records-v2` | Navigate call numbers using bytewise lexical order. | Node traversal demonstrates the documented `A-2 < A-10` comparator. |
| `bst-network-port-leases-v2` | Reserve closed port ranges and find the first free port. | Subtree `max_end` skips occupied ranges while preserving the inclusive bound. |
| `bst-parking-free-intervals-v2` | Coalesce released ranges and split them on occupancy. | Touching intervals merge through node deletion/insertion; occupancy splits the owning node. |
| `bst-price-level-book-v2` | Replace/consume price levels and find the best affordable level. | Exact-budget predecessor succeeds; consumption to zero deletes the node. |
| `bst-scoreboard-player-ranks-v2` | Rank players by descending score and lexical ID. | Subtree size supplies one-based rank; erase performs no auxiliary-map lookup. |
| `bst-sensor-hysteresis-rules-v2` | Select the greatest enter threshold active at a value. | Floor traversal preserves equality and the documented hysteresis payload. |
| `bst-ticket-priority-ledger-v2` | Order tickets by priority/number and query an owner's next ticket. | Composite-key close locates/deletes the exact ticket without an auxiliary map. |
| `bst-transit-service-board-v2` | Add/cancel departures and query time windows/next service. | Lower-bound traversal uses lexical route ties and exact pair cancellation. |
| `bst-semver-release-catalog-v2` | Publish/withdraw versions and find the latest compatible release. | Predecessor traversal is bounded to the requested major version. |
| `bst-warehouse-bin-inventory-v2` | Store bins and find the least-ID bin meeting capacity. | Subtree `max_capacity` guides selection and remains exact after deletion. |

The family/duplicate screen must prove these are materially distinct state
models and negative-domain contracts. A normalized semantic duplicate is
replaced or excluded; it is never retained because the nouns differ.

## Common real-BST implementation contract

Every replacement class must contain an authoritative private nested node and
root ownership equivalent to:

```cpp
struct Node {
  Key key;
  Payload payload;
  std::unique_ptr<Node> left;
  std::unique_ptr<Node> right;
  std::size_t subtree_size;
};
std::unique_ptr<Node> root_;
```

Interval roots add exact `max_end`; energy adds checked `subtree_sum`; exam
adds positive multiplicity and counts occurrences in subtree size; scoreboard
uses subtree size for rank; warehouse adds exact `max_capacity`. Other roots
retain exact node-count `subtree_size` only.

Copy operations are deleted; move operations and the destructor are out of
line. All affected metadata is recomputed on recursive return. Two-child
deletion transfers the complete in-order-successor payload, removes that
successor from the right subtree, and recomputes every ancestor.

The tree is intentionally unbalanced. The structural probe must observe both
the height-31 chain produced by increasing comparator keys 1 through 31 and
the height-4 tree produced by
`8,4,12,2,6,10,14,1,3,5,7,9,11,13,15`. It must then observe leaf,
one-child, and two-child deletion with exact in-order results.

## Public task-contract requirements

Each task exposes its domain API rather than generic public node operations.
The exact API in the normative specification must define:

- value and payload types plus exact key comparator;
- valid and invalid input;
- duplicate, absent, and empty behavior;
- successful and rejected mutation effects;
- range endpoint policy, ordering, and ties;
- checked overflow behavior;
- two public boundary examples;
- editable response order `<task-id>.h`, then `<task-id>.cpp`.

Documented invalid input never throws and never partially mutates state.
Returned records are copies. Output vectors follow the declared comparator.
Reversed ranges are never silently normalized.

## Primary verification requirements

The owner must provide a private `BstInvariantProbe` under
`CURRICULUM_TESTING` that reads the actual root and nodes. It validates unique
acyclic reachability, strict comparator bounds, exact height/node/occurrence
counts, in-order payload equality, subtree size, and all task-specific
augmentation after every accepted and rejected mutation.

Every root uses its fixed specification seed for exactly 4,096 deterministic
operations. A private sorted-vector value oracle implements published behavior
independently and compares every return value and complete in-order result.
That vector is permitted only as test-oracle state, never as production index.

The focused suite must deliberately reject at least:

- the current `std::set` wrapper;
- map/unordered-container delegation;
- a sorted-vector index with a fake or dummy node;
- a degenerate node declaration with hard-coded/precomputed work;
- invalid child ordering;
- stale augmentation on augmented roots;
- the root-specific boundary/tie/duplicate/overflow error.

The stable primary failure is `invariant_not_enforced`. The implementation may
enter `implemented` only after every produced root records
`primary_core_objective: achieved` with source and deterministic structural
evidence.

## Secondary materialization requirements

Only after the primary core passes, complete these local-family gates:

1. self-contained visible docs and coherent incomplete header/source starters;
2. an independent readable node-tree reference mapping both editable files;
3. exactly named visible/private Catch roles and eight positive discovered
   cases in both normal and fresh sanitizer builds;
4. strict whole-file parsing/application with no prose, missing, duplicate,
   unknown, or unsafe paths;
5. role-correct config/provenance with source, authoring, resolved license,
   family, revision, parent, generator/spec/support, and benchmark identities;
6. the checked-in `exercism-catch-v1` C++17 scaffold;
7. locked normal and fresh ASan/UBSan receipts in the immutable grader named by
   the normative specification;
8. whole-slug, content, semantic holdout, duplicate-task, and family screens.

Prompt-boundary success and current host/focused tests are secondary evidence;
they cannot establish the core implementation or locked oracle status.

## Ownership and materialization result

The owning source remains
`src/w8_biayn/integrations/moonlight_binary_search_tree_aider_tasks.py`; its
focused regression remains
`tests/test_moonlight_binary_search_tree_aider_tasks.py`. Implementation must
change the owner and focused tests, then regenerate; generated roots are never
hand-edited.

Output:

```text
.w8-biayn/data/aider-tasks-reverify/aider-dsa/binary-search-tree/
```

The owner exposes these specification-required commands:

```bash
uv run python -m w8_biayn.integrations.moonlight_binary_search_tree_aider_tasks \
  --out .w8-biayn/data/aider-tasks-reverify/aider-dsa/binary-search-tree \
  --force --verify-core

uv run pytest -q tests/test_moonlight_binary_search_tree_aider_tasks.py

uv run python -m w8_biayn.integrations.moonlight_binary_search_tree_aider_tasks \
  --out .w8-biayn/data/aider-tasks-reverify/aider-dsa/binary-search-tree \
  --force --verify
```

The 20 roots were regenerated through that owner on 2026-07-18. The focused
test and prompt-boundary/family screens passed. Every reference ran its eight
named tests in both normal and fresh ASan/UBSan builds in
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
with network disabled. The 20 receipts and manifest record equal counts of
eight; the legacy preparation target remains preserved v1 audit evidence.

## Ordered implementation and completion boundary

1. Freeze all current tree hashes/remedy records and resolve license; stop a
   rejected root before generation.
2. Implement authoritative nodes, recursive operations, deletion, and
   augmentation in a new v2 renderer.
3. Implement structural probes, deterministic traces, behavior oracles, and
   false-substitute fixtures; require the primary result `achieved`.
4. Add the exact public contracts, starters, independent references, roles,
   metadata, Catch scaffold, and strict whole-file application.
5. Run locked normal and fresh sanitizer oracle/application ladders.
6. Run benchmark and family/duplicate screens; reject or replace failures
   without renaming around them.
7. Mark `local_family_verified` only after every required local gate passes.

The only valid forward path is:

```text
unreviewed -> audited -> planned -> implemented -> oracle_verified
  -> semantically_admitted -> local_family_verified
```

The v2 roots have `verified` remedy records and their family screen passes.
This curriculum does not claim training suitability, release readiness, or
benchmark improvement. It creates no JSONL,
token/mask evidence, split, export, consumer verification, training
authorization, paid call, or benchmark run.
