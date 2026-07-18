# Balanced Search Tree Curriculum: Topic 1, Subtask 3

**Status:** clean-room curriculum and implementation-design source. This is a
planning inventory of local candidate roots, not an assertion that any
materialized root conforms to this document. It does not claim
`local_family_verified`, SFT admission, a dataset release, training
authorization, or benchmark uplift.

This curriculum is the third subtask under **Linked Structure Invariants**:
real AVL and red-black tree implementations. The deterministic implementation
contract is
[`docs/aider-tasks-spec/aider-dsa/balanced-search-tree.md`](../../aider-tasks-spec/aider-dsa/balanced-search-tree.md).
That specification is normative: if this curriculum and the specification ever
disagree, the specification controls. In particular, it replaces earlier
ordered-set-wrapper interpretations of these roots.

The official Aider Polyglot C++ `binary-search-tree` task is a permanent
benchmark holdout. Do not copy its wording, API, tests, reference,
implementation strategy, prompts, or close semantic variants into this family.

Use this with:

- `docs/AIDER_SFT_SCOPE.md`
- `docs/AIDER_TASK_MATERIALIZATION_GUIDE.md`
- `docs/aider-tasks-spec/Original-specs.md`
- `docs/aider-tasks-spec/verify-and-remedy.md`
- `docs/aider-tasks-spec/aider-dsa/balanced-search-tree.md`

## Clean-room boundary

Online AVL and red-black references are useful only for private concept study.
They are not a source inventory and may not be copied into a root. Every
interface, starter, reference, test, documentation example, and provenance
record must be newly authored in this repository, with explicit license/usage
terms and a benchmark-separation decision.

Generated roots belong only beneath:

```text
.w8-biayn/data/aider-tasks/aider-dsa/balanced-search-tree/
```

They remain local candidate material. References, private tests, metadata,
CMake files, and oracle receipts are private task assets and must not enter a
model prompt, JSONL row, split, export, or dataset-release claim.

## Curriculum objective

Each `avl-*` root teaches a repo-owned AVL tree with explicit node ownership,
stored height, and rebalancing after every insertion and deletion. Roots that
need rank/select also store subtree size. Each `rb-*` root teaches a repo-owned
red-black tree with explicit color and parent/child links (or equivalent
sentinels) plus standard insertion and deletion fix-up.

No indexed state may use `std::set`, `std::map`, `std::multiset`,
`std::unordered_*`, GNU PBDS, Boost containers, or a third-party tree. A
reference must independently implement the same tree kind; it may not be an
answer-shaped copy of the starter. A sorted vector or simple record list is
permitted only as a private behavior oracle.

Every root has exactly two editable files, `<task-id>.h` followed by
`<task-id>.cpp`, and the assistant response is exactly one complete whole-file
listing for each in that order. Public declarations are in namespace
`curriculum`, target C++17, perform no I/O, and are deterministic. IDs are
nonempty ASCII `[A-Za-z0-9_-]`; invalid IDs reject without mutation. Positive
keys and quantities reject zero and negative values, while reversed ranges
never swap endpoints.

## Root inventory and fixed public contracts

The following inventory is exhaustive. The exact declarations and all behavior
rules are in sections B1–B20 of the normative specification; the summary here
is intentionally not a substitute for those rules.

| ID | Tree | Public class | Distinct observable capability |
| --- | --- | --- | --- |
| `avl-live-leaderboard` | AVL | `LiveLeaderboard` | Player score upserts, one-based rank, and descending top entries with score/ID ties. |
| `avl-api-rate-limits` | AVL | `ApiRateLimits` | Threshold-keyed rate-limit replacement, floor resolution, and inclusive windows. |
| `avl-appointment-slots` | AVL | `AppointmentSlots` | Non-overlapping half-open bookings and earliest forward-gap allocation. |
| `avl-inventory-restock` | AVL | `InventoryRestock` | SKU replacement with reorder-level/ID ordering and applicable-rule selection. |
| `avl-memory-free-ranges` | AVL | `MemoryFreeRanges` | Non-overlapping free-block release/coalescing and lowest-start first-fit allocation. |
| `avl-coupon-thresholds` | AVL | `CouponThresholds` | Threshold-keyed coupon payloads and best eligible coupon selection. |
| `avl-game-matchmaking` | AVL | `GameMatchmaking` | Player ratings with self exclusion and deterministic nearest-opponent ties. |
| `avl-energy-tariffs` | AVL | `EnergyTariffs` | Usage breakpoints with active half-open tariff intervals. |
| `avl-shipping-weight-bands` | AVL | `ShippingWeightBands` | Disjoint, nonadjacent weighted bands and containment quotes. |
| `avl-library-holds` | AVL | `LibraryHolds` | Stable priority/placement ordering and atomic eligible-hold promotion. |
| `rb-order-book` | Red-black | `OrderBook` | Bid-level replacement, strict-below limit selection, and descending listing. |
| `rb-file-version-index` | Red-black | `FileVersionIndex` | Revision/hash replacement, predecessor lookup, and inclusive revision ranges. |
| `rb-reservation-directory` | Red-black | `ReservationDirectory` | Unique reservation IDs/codes and deterministic nearest-code lookup. |
| `rb-medication-schedule` | Red-black | `MedicationSchedule` | Neutral numeric schedules with same-time ID ordering and inclusive windows. |
| `rb-access-control-rules` | Red-black | `AccessControlRules` | Priority/ID ordered allow-or-deny rule payload resolution. |
| `rb-cargo-manifest` | Red-black | `CargoManifest` | Cargo payload replacement, lookup, and increasing ID ranges. |
| `rb-metric-percentiles` | Red-black | `MetricPercentiles` | Duplicate-aware observations, multiplicity-aware rank selection, and percentile endpoints. |
| `rb-travel-fare-table` | Red-black | `TravelFareTable` | Budget-keyed fare payloads and best eligible fare selection. |
| `rb-audit-event-index` | Red-black | `AuditEventIndex` | Immutable event recording, idempotent redaction, retention removal, and ranges. |
| `rb-support-escalations` | Red-black | `SupportEscalations` | Open-case reprioritization and atomic next-case selection with stable ties. |

This is a 20-root planning inventory, not a quota. A duplicate-family or
benchmark-contamination screen can reject or require replacement of a root;
the root must not be retained merely through a domain rename.

## Structural and test contract

All private tests compile with `CURRICULUM_TESTING` and call
`validate_for_test()` after every mutation. The test-only `TreeCheck` exposes
only validation status, node count, and AVL height or RB black height. It must
not expose nodes, colors, or mutation operations.

- AVL validation proves ordered unique ownership, correct stored heights and
  required subtree sizes, and a child-height difference of at most one. Every
  nonempty tested state also satisfies
  `height <= 2 * ceil_log2(nodes + 1)`.
- RB validation proves ordered unique ownership, a black root, no red-red
  edge, equal black height, and valid parent links.
- Root-specific tests cover the public API's documented invalid, duplicate,
  absent, empty, ordering, tie, range, and overflow behavior. They also cover
  rotations/rebalancing or RB insertion/deletion fix-up as applicable.
- Every root runs the exact deterministic 10,000-operation trace defined by
  its test, seeded by `state = state * 1664525U + 1013904223U`. Public behavior
  is checked against a sorted-vector or explicit-record-list oracle and
  `TreeCheck` is checked after every operation.
- Private negative fixtures must reject the prior `std::set` wrapper, a sorted
  vector implementation, and a deliberately degenerate BST. A label such as
  “LL/RR/LR/RL” without structural validation is not evidence of balancing.

Visible documentation must be sufficient to implement the public contract: it
states types and ownership, method effects and return values, validation,
duplicate/absent/empty behavior, ordering/ties, mutation rules, and at least
two public examples including a boundary case. It must not describe private
tests, reference code, or local implementation status.

## Required materialization and evidence

The owner is
`src/w8_biayn/integrations/moonlight_balanced_search_tree_aider_tasks.py`.
It must be a local balanced-tree renderer, not an import or adaptation of a
binary-search-tree renderer. It emits the exact APIs, task-specific starters,
independent references, public and private Catch tests, role metadata, and a
balanced-tree-named CMake project.

For each root, `.meta/config.json` records both editable files, every test
source, both `.meta/example.*` files, `source` as
`newly-authored-in-repository`, nonempty attribution, and all role mappings.
Provenance records the curriculum path and hash, generator revision, task ID,
family ID, clean-room authoring method, license/usage terms, and
benchmark-separation decision. Every path is relative, safe, existing, and
non-conflicting.

CMake uses C++17, explicit `Unix Makefiles`, strict GCC/Clang warnings, the
repo-owned Catch support bundle by digest, named `visible` and `hidden` CTest
entries, and `EXERCISM_RUN_ALL_TESTS=1`. It must not use an `ALL` target to
hide test execution. Production solution compilation does not define
`CURRICULUM_TESTING`.

The repository-owned verifier must regenerate first, then run the reference in
a clean locked normal build and fresh locked ASan/UBSan build. It separately
discovers tests, requires a positive equal normal/sanitizer count, and writes
redacted receipts binding the tree hash, reference mapping, generator revision,
image identity, compiler path/version/hash, CMake and Catch digests, and
sandbox policy. Missing locked prerequisites are recorded as `not_completed`;
a host-only result is not locked-oracle evidence.

Before any root can reach `local_family_verified`, run whole-slug and semantic
benchmark-contamination screening plus duplicate-contract family screening.
The prompt-boundary check must prove that only visible documentation and the
two declared editable starter files reach the model.

## Current handoff state

Existing generated artifacts, if present, require generator-owned remediation
and regeneration to meet the deterministic specification. Do not hand-edit
anything under `.w8-biayn/data/aider-tasks/`. A future implementation follows
the per-root remedy state machine in `verify-and-remedy.md`, records the
strongest truthful evidence, and may mark this family `local_family_verified`
only after regeneration, prompt-boundary validation, locked normal and fresh
ASan/UBSan reference evidence, and both screening gates pass.

The local materialization command remains:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_balanced_tree_aider_tasks.sh --verify
```

It creates only the local family root. It does not admit, split, export, or
claim a primary SFT dataset release.
