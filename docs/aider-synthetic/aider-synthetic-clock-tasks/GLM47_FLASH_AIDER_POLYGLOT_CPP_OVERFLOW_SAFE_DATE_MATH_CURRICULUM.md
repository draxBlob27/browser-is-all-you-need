# Overflow-Safe Date Math Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum teaches validated Gregorian arithmetic under explicit supported
ranges: checked day/month multiplication and addition, leap-aware conversion,
failure-before-wrap semantics, range-bound diagnostics, and atomic state
updates. It does not implement a generic date library or a fixed future
timestamp offset.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

Every official Aider Polyglot C++ root is a permanent holdout. In particular,
do not reuse `gigasecond`, `meetup`, or `clock` wording, API, types,
examples, tests, reference implementation, or model outputs. Do not create a
renamed exercise whose main behavior is adding one fixed offset to a datetime
or finding a weekday occurrence.

The proposals below are **not yet proven decontaminated**. They embed checked
calendar arithmetic in independently authored domain policies, bounded record
sets, and typed diagnostics. Before admission, run the shared whole-slug
benchmark denylist and semantic-contamination checks; reject and backfill every
near match. Each surviving root must differ from holdout families in at least
three dimensions: public API/output, offset/policy source, state/collection
model, overflow/range behavior, and domain diagnostic.

Inputs must be caller supplied and deterministic: no host clock, time-zone or
calendar API dependence, filesystem/network access, threads, or randomness.

## Online Material Status

Safe date-arithmetic examples are useful only for private concept study or
licensed source discovery. They are not a drop-in SFT inventory. Each candidate
must be newly authored in C++17 with independent task text, starter API,
reference, examples, and tests, then pass provenance, license, oracle,
sanitizer, contamination, split, rendering, and release gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from holdouts |
|---|---|---|---|
| `safe-date-retention` | Retention deadline validator | Compute archive purge/review deadlines from policy durations within an allowed year range, returning range-exceeded diagnostics. | Uses retention records and multi-stage policy results, not a fixed offset. |
| `safe-date-supply-chain` | Supply-chain lead-time planner | Advance purchase orders by variable manufacturing and transit durations, rejecting any intermediate date outside the supported calendar range. | Processes order-stage records with intermediate-overflow proof. |
| `safe-date-lease-amendment` | Lease amendment checker | Apply ordered month/day amendments to lease dates atomically and explain the first amendment that would overflow. | Uses mutable amendment state with rollback semantics. |
| `safe-date-medical-protocol` | Medical protocol horizon | Generate bounded follow-up milestones from treatment policy while refusing unsafe dates beyond a clinical data horizon. | Produces several policy milestones and clinical range status. |
| `safe-date-audit-export` | Audit export window | Validate export windows formed by signed date adjustments and retain only windows entirely inside a compliance archive range. | Filters record collections under a containment policy. |
| `safe-date-manufacturing-cycle` | Manufacturing cycle forecast | Advance equipment service cycles by calendar months and usage-derived day buffers with checked clamp behavior. | Combines two offset sources and equipment lifecycle policy. |
| `safe-date-library-preservation` | Library preservation schedule | Calculate inspection and treatment dates for collections, flagging materials whose preservation policy cannot be represented safely. | Joins collection metadata to bounded policy schedules. |
| `safe-date-grant-reporting` | Grant reporting calendar | Recalculate report due dates after approved extensions, refusing an extension that moves any dependent milestone out of range. | Uses dependency graph-like milestone records and atomic rejection. |
| `safe-date-satellite-ephemeris` | Satellite ephemeris archive | Partition requested observation dates into representable and unsupported archive segments under a declared epoch horizon. | Uses archive segmentation and range classification, not civil-time conversion. |
| `safe-date-voucher-expiry` | Voucher expiry ledger | Apply issuance, suspension, and reactivation durations with a maximum representable expiry and stable per-voucher diagnostics. | Implements lifecycle precedence and per-record checked updates. |

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Names,
types, examples, and algorithms must be independently authored during
materialization.

### `safe-date-retention`

Policies have positive review/purge durations and an explicit supported year
range. If a purge computation is unsupported, do not return a wrapped date or
silently omit its review milestone.

### `safe-date-supply-chain`

Each stage may use day or calendar-month policy offsets. Validate every
intermediate result, not only the final delivery date, and identify the first
stage that cannot be represented.

### `safe-date-lease-amendment`

Amendments have stable sequence IDs and may add or subtract within documented
bounds. A failed amendment leaves the lease at its prior valid date and must
not prevent a later diagnostic from identifying the same failure cause.

### `safe-date-medical-protocol`

Clinical policy specifies a bounded horizon and end-of-month behavior. Define
whether a milestone exactly at the horizon is valid and whether a missing
treatment-policy category is invalid or an explicit no-plan result.

### `safe-date-audit-export`

Windows have a declared endpoint convention. Signed adjustment may create an
invalid/reversed window; report it distinctly from a well-formed window that
merely lies outside the archive range.

### `safe-date-manufacturing-cycle`

Usage buffers and month cycles are independently validated. Define the order of
month clamping and day buffering, and distinguish calendar-range overflow from
an unsupported equipment policy.

### `safe-date-library-preservation`

Collection items have stable IDs and policy classes. An unknown class, invalid
source date, or range-exceeded treatment date needs a separate diagnostic
without suppressing valid items from the schedule.

### `safe-date-grant-reporting`

Milestones have dependencies and stable IDs. An extension affecting several
dependent dates must either update all validly or update none; define
deterministic order for reporting the blocking dependency.

### `safe-date-satellite-ephemeris`

The archive epoch horizon is caller supplied. Define how to split a requested
span that partly exceeds the horizon and whether an empty representable segment
is returned or treated as fully unsupported.

### `safe-date-voucher-expiry`

Lifecycle events have stable IDs and event order. Specify whether suspension
pauses expiry, shifts it, or overrides it, and ensure a rejected reactivation
does not modify the last valid expiry state.

## Materialization Requirements

Every candidate needs a task-specific C++17 public API. Do not expose generic
`add_days`, `add_months`, `safe_date_add`, or a date-library replacement
as the assignment. The starter must expose domain records, supported ranges,
policy inputs, structured results, and explicit invalid-input behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh locked sanitizer build; and
6. shared-denylist and semantic-contamination evidence.

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

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate found to be
a close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.

