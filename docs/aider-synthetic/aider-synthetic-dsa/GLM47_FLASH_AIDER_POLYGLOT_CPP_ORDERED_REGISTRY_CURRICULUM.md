# Ordered Registry Curriculum: Decontaminated Grade-School Capability

Status: locally reverified v2 curriculum. The v1 generated family remains
preserved as audit input. The v2 roots are local task artifacts only; they are
not admitted SFT roots, an online dataset, or benchmark evidence.

The official Aider Polyglot C++ `grade-school` task is a permanent benchmark
holdout. This document does **not** propose twenty renamed roster exercises.
It targets the more general capability—maintaining an ordered registry under
identity, grouping, membership, reassignment, and query constraints—through
materially different domain contracts.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

Do not use the holdout task's wording, API, classes, field names, examples,
tests, reference implementation, expected ordering rules, or student/grade
scenario. Do not construct a source candidate by paraphrasing or translating
the holdout.

Each candidate below must be independently authored from a new behavior
specification and must materially differ in at least three of these dimensions:

- entity model and stable identity;
- group meaning and membership cardinality;
- ordering key and tie-breaking;
- mutation model, such as reassignment, capacity, expiry, or state transition;
- query shape, aggregate, or error behavior;
- visible C++ API and data representation.

Before admission, run the repository's whole-slug benchmark denylist and
semantic contamination checks against all official Aider C++ roots. A
near-match, including a straightforward group-and-sort registry that merely
renames the holdout, is rejected. Preserve the rejection evidence and backfill
with a new independently designed candidate; never weaken the checker.

## Online Material Status

Online collection and registry exercises are useful for private concept study
or source discovery only. They are not a drop-in SFT source inventory: every
external source needs explicit license and semantic-contamination review.

The following tasks materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Remediated Decontaminated Tasks

| V2 ID | Task | Distinct primary mechanism |
|---|---|---|
| `registry-audit-retention` | Audit retention | Expiry/hold ledger with eligibility-gated erasure (`repair-in-place`). |
| `customs-clearance-workflow` | Cargo customs | Explicit filed→inspected→cleared finite-state machine. |
| `triage-priority-board` | Clinic triage | Mutable clinical priority with destructive next-patient selection. |
| `session-seat-waitlist` | Conference seats | Separate seated/waiting states with deterministic promotion. |
| `device-heartbeat-index` | Device fleet | Monotonic heartbeat index independent of deployment-ring moves. |
| `rollout-token-ring` | Feature rollout | Clockwise lower-bound routing on a mutable consistent-hash token ring. |
| `gate-conflict-scheduler` | Flight gates | Compatibility-aware half-open interval calendars. |
| `dish-allergen-catalog` | Food allergens | Canonical set storage and set-disjointness queries. |
| `proposal-review-matcher` | Grant reviews | Separate conflict and assignment edge relations. |
| `room-stay-calendar` | Hotel rooms | Multi-stay room interval calendars and earliest-free search. |
| `service-incident-queue` | Incident routing | Maintained per-service priority indices under escalation/removal. |
| `copy-loan-ledger` | Library loans | One-copy loan lifecycle with forward-only renewals. |
| `crew-workload-ledger` | Maintenance crews | Weighted-capacity conservation and atomic reassignment. |
| `asset-custody-history` | Museum assets | Append-only event history with predecessor-at-time lookup. |
| `permit-expiry-wheel` | Parking permits | Extendable modular expiry wheel with stale absolute-due suppression. |
| `shipping-rate-resolver` | Shipping contracts | Multi-criterion overlapping interval resolution. |
| `billing-cycle-counter` | Subscription plans | Reconciled two-dimensional plan/cycle aggregates. |
| `sla-escalation-heap` | Support escalations | Owned indexed binary heap with sift-up/down and removals. |
| `vaccine-lot-fefo` | Vaccine inventory | Transactional multi-lot first-expiry-first-out allocation. |
| `warehouse-batch-splitter` | Warehouse batches | Unit conservation across split/merge and weighted zone capacity. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose an API shaped
like a generic group-to-sorted-name roster. Include each task's distinct
identity, ordering, constraints, transition rules, and query result types in
the starter interface.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

The v1 roots failed the independence gate: all twenty rendered the same
`Entry` vector and register/transition/query implementation. Deterministic
disposition therefore retained only the lexicographically first salvageable
root ID (`registry-audit-retention`) and replaced the other nineteen. A v2
root must fail verification if the legacy generic representation returns.

Hidden tests and the owner-side core screen cover:

- identity collision and duplicate-registration behavior;
- the task-specific reassignment, cancellation, expiry, capacity, or state
  transition semantics;
- ordering and tie-breaking over multi-field keys;
- invalid cross-group transitions and failed operations with no state mutation;
- removal of the final member of a group and empty-query behavior;
- aggregate/count behavior where exposed;
- deterministic operation traces checked after every operation against an
  independent vector/value oracle, including every public operation class;
- one compiled topic-specific false substitute whose executed tests must reject
  the incorrect logic; and
- a final contamination screen proving the candidate remains outside the
  benchmark holdout family.

## Materialization And Evidence

The owner is
`src/w8_biayn/integrations/moonlight_ordered_registry_aider_tasks.py`, with
task-specific renderers in `moonlight_ordered_registry_cases.py`. It writes
only the parallel reverify root:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_ordered_registry_aider_tasks.sh \
  --force --verify-core --verify
```

The legacy root is never regenerated. Per-root v1/v2 tree hashes and
dispositions live under the reverify sibling `.state/remedy/`; the
materialization manifest records prompt, role/reference, unique-family, core,
and all-26-holdout semantic screens. Oracle evidence uses the immutable
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
image with networking disabled. Every v2 reference discovered and passed two
normal and two fresh ASan/UBSan CTests.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
