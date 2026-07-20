# Overflow-Safe Date Math Curriculum: Decontaminated Capability

Status: v2 local-family remediation curriculum. This document defines ten
counted local candidates under the user-authorized 8–12 hard-count bound. It
does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum teaches validated Gregorian arithmetic under explicit supported
ranges: checked day/month multiplication and addition, leap-aware conversion,
failure-before-wrap semantics, range-bound diagnostics, and atomic state
updates. It does not implement a generic date library or a fixed future
timestamp offset.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

Every official Aider Polyglot C++ root is a permanent holdout. In particular,
do not reuse `gigasecond`, `meetup`, or `clock` wording, API, types,
examples, tests, reference implementation, or model outputs. Do not create a
renamed exercise whose main behavior is adding one fixed offset to a datetime
or finding a weekday occurrence.

The v2 candidates must pass the artifact-derived screen against all 26 bound
official C++ holdouts before `local_family_verified`. Whole-slug screening is
only the first check; normalized docs, APIs, reference control flow, and tests
must also remain separate. Each counted pair in this family must differ in all
seven hard-rule dimensions specified in
`docs/aider-tasks-spec/aider-text-grid-reshaping/overflow-safe-date-math.md`.

Inputs must be caller supplied and deterministic: no host clock, time-zone or
calendar API dependence, filesystem/network access, threads, or randomness.

## Online Material Status

Safe date-arithmetic examples are useful only for private concept study or
licensed source discovery. They are not a drop-in SFT inventory. Each candidate
must be newly authored in C++17 with independent task text, starter API,
reference, examples, and tests, then pass provenance, license, oracle,
sanitizer, contamination, split, rendering, and release gates.

## Counted V2 Tasks

| ID | Task | Visible contract | Deliberate separation from holdouts |
|---|---|---|---|
| `retention-stage-calculator` | Retention stage calculator | Compute review, then purge, with checked year-to-month conversion and batch-atomic commit. | Two-stage calculation with multiplication guards, not a generic record transform. |
| `checked-stage-pipeline` | Checked supply-stage pipeline | Evaluate a branching stage DAG using maximum-predecessor completion and mixed month/day lead times. | Critical-path graph evaluation with intermediate overflow proof. |
| `transactional-lease-amendments` | Transactional lease amendments | Fold sequence-numbered month/day amendments in caller order and roll back on the first unsafe step. | Ordered transactional state, not sorted record scheduling. |
| `clinical-milestone-expansion` | Clinical milestone expansion | Expand labeled cumulative or treatment-relative day gaps through an inclusive horizon. | Indexed prefix/direct expansion with atomic failure identity. |
| `safe-date-audit-export` | Audit export window classifier | Shift closed windows and stably classify accepted, reversed, outside, or unrepresentable rows. | Multi-bucket interval classification and first-rejection selection. |
| `bounded-service-recurrence` | Bounded service recurrence | Generate per-machine recurrences and merge them globally by date and machine ID. | Stateful k-way chronological recurrence merge. |
| `preservation-policy-join` | Preservation policy join | Join items to unique policy codes and keep ordered per-item diagnostics alongside valid rows. | Validated two-table join with partial item admission. |
| `checked-grant-dependency-shift` | Checked grant dependency shift | Propagate approved extensions through a milestone DAG using maximum inherited delay. | Topological delay propagation with atomic commit. |
| `epoch-span-partitioner` | Epoch span partitioner | Split one closed requested span into before, representable, and after segments. | Interval intersection/segmentation without fixed-offset scheduling. |
| `voucher-lifecycle-ledger` | Voucher lifecycle ledger | Replay issue, suspend, reactivate, and redeem events with checked paused-duration expiry shifts. | Event-sourced finite-state transition validation. |

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Names,
types, examples, and algorithms must be independently authored during
materialization.

### `retention-stage-calculator`

Policies have positive review/purge durations and an explicit supported year
range. If a purge computation is unsupported, do not return a wrapped date or
silently omit its review milestone.

### `checked-stage-pipeline`

Each stage may use day or calendar-month policy offsets. Validate every
intermediate result, not only the final delivery date, and identify the first
stage that cannot be represented.

### `transactional-lease-amendments`

Amendments have stable sequence IDs and may add or subtract within documented
bounds. A failed amendment leaves the lease at its prior valid date and must
not prevent a later diagnostic from identifying the same failure cause.

### `clinical-milestone-expansion`

Clinical policy specifies a bounded horizon and end-of-month behavior. Define
whether a milestone exactly at the horizon is valid and whether a missing
treatment-policy category is invalid or an explicit no-plan result.

### `safe-date-audit-export`

Windows have a declared endpoint convention. Signed adjustment may create an
invalid/reversed window; report it distinctly from a well-formed window that
merely lies outside the archive range.

### `bounded-service-recurrence`

Usage buffers and month cycles are independently validated. Define the order of
month clamping and day buffering, and distinguish calendar-range overflow from
an unsupported equipment policy.

### `preservation-policy-join`

Collection items have stable IDs and policy classes. An unknown class, invalid
source date, or range-exceeded treatment date needs a separate diagnostic
without suppressing valid items from the schedule.

### `checked-grant-dependency-shift`

Milestones have dependencies and stable IDs. An extension affecting several
dependent dates must either update all validly or update none; define
deterministic order for reporting the blocking dependency.

### `epoch-span-partitioner`

The archive epoch horizon is caller supplied. Define how to split a requested
span that partly exceeds the horizon and whether an empty representable segment
is returned or treated as fully unsupported.

### `voucher-lifecycle-ledger`

Lifecycle events have stable IDs and event order. Specify whether suspension
pauses expiry, shifts it, or overrides it, and ensure a rejected reactivation
does not modify the last valid expiry state.

## Materialization Requirements

Exactly ten roots are counted; this is a binding local gate within the
user-authorized 8–12 range. Every candidate needs a task-specific C++17 public API. Do not expose generic
`add_days`, `add_months`, `safe_date_add`, or a date-library replacement
as the assignment. The starter must expose domain records, supported ranges,
policy inputs, structured results, and explicit invalid-input behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh sanitizer build in the pinned network-disabled
   Docker sanity image;
6. one buildable and executed topic-specific false substitute;
7. complete all-pairs evidence for every one of the 45 unordered family pairs
   in all seven hard-rule dimensions; and
8. all 260 emitted-root-to-official-holdout comparisons.

Hidden tests must cover, where applicable:

- exact minimum/maximum supported dates and one-step-outside failures;
- leap-year February, month-end clamp, century, and year-end transitions;
- checked large positive/negative offsets and intermediate-result overflow;
- equality at archive, clinical, retention, and expiry range boundaries;
- empty/singleton collections, duplicate IDs, stable ties, and atomic rollback;
- invalid/reversed windows, dependent milestone failures, and lifecycle
  precedence;
- randomized bounded records checked against a small independent checked
  proleptic-Gregorian oracle; and
- a final contamination screen proving the root remains outside every benchmark
  family, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate found to be
a close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.
