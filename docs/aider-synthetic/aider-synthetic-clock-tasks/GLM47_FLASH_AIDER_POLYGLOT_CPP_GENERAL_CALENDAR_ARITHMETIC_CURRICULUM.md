# General Calendar Arithmetic Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum develops general Gregorian calendar arithmetic: validated civil
dates, leap-aware month lengths, add/subtract day and month operations,
end-of-month rollover policy, ordinal conversion, and checked range handling.
The capability appears inside domain-specific policies and collections, not as a
bare date-library replacement.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

Every official Aider Polyglot C++ root is a permanent holdout. In particular,
do not reuse `gigasecond`, `meetup`, or `clock` wording, API, types,
examples, tests, references, or model outputs. Do not author a near-copy that
only adds a fixed offset, finds a weekday occurrence in a month, or presents a
generic `Date::add_days` exercise.

The proposals below are **not yet proven decontaminated**. They use calendar
arithmetic within independently authored policy, allocation, lifecycle, and
diagnostic contracts. Before admission, run the shared whole-slug benchmark
denylist and semantic-contamination checks; reject and backfill every near
match. Each surviving root must differ from holdout families in at least three
dimensions: public API/output, record/state model, calendar policy, domain
operation, and invalid-input/result behavior.

Inputs must be caller supplied and deterministic: no host clock, time-zone or
calendar API dependence, filesystem/network access, threads, or randomness.

## Online Material Status

Calendar-arithmetic examples are useful only for private concept study or
licensed source discovery. They are not a drop-in SFT inventory. Each candidate
must be newly authored in C++17 with independent task text, starter API,
reference, examples, and tests, then pass provenance, license, oracle,
sanitizer, contamination, split, rendering, and release gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from holdouts |
|---|---|---|---|
| `calendar-subscription-cycle` | Subscription cycle manager | Advance subscriber renewal dates by policy months using an explicit end-of-month clamp and report proration-boundary diagnostics. | Manages account records and a rollover policy, not a fixed future offset. |
| `calendar-harvest-plan` | Harvest plan rollover | Shift crop windows by season months while preserving or clamping planting day and identifying invalid windows. | Transforms a collection of agricultural windows with domain validation. |
| `calendar-clinic-followup` | Clinic follow-up planner | Generate permitted follow-up dates from care-plan intervals, blackout dates, and a maximum scheduling horizon. | Combines month arithmetic with exclusions and a plan result. |
| `calendar-inventory-expiry` | Inventory expiry reconciler | Reconcile manufacture dates, shelf-life months, and recall dates into active, expiring, or expired product states. | Joins product lifecycle records and policy-specific status. |
| `calendar-contract-amendment` | Contract amendment ledger | Apply ordered amendments that extend, shorten, or suspend contract periods while rejecting conflicting effective dates. | Uses a mutable amendment log with deterministic conflict diagnostics. |
| `calendar-vacation-allocation` | Vacation allocation checker | Allocate requested leave spans against annual balances, carry-over rules, and organization closure dates. | Integrates date spans with balances and closure policy. |
| `calendar-maintenance-rotation` | Maintenance rotation scheduler | Compute recurring service windows every N calendar months and flag equipment that falls outside its allowed service range. | Works on recurrence records and compliance status rather than weekday lookup. |
| `calendar-licence-grace` | Licence grace evaluator | Classify licence renewal submissions using expiry, grace, and reinstatement calendar rules with explicit equality semantics. | Produces regulatory-style outcome diagnostics from several policy dates. |
| `calendar-release-train` | Release train planner | Move release milestones by approved month shifts, preserve ordering, and explain collisions after end-of-month adjustment. | Repairs a milestone collection under ordering and collision constraints. |
| `calendar-lease-portfolio` | Lease portfolio report | Aggregate lease start/end records into month-bucket occupancy and identify gaps, overlaps, and unsupported date ranges. | Uses portfolio aggregation and interval diagnostics. |

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Names,
types, examples, and algorithms must be independently authored during
materialization.

### `calendar-subscription-cycle`

Define the clamp policy for dates such as the 29th–31st and whether a later
renewal resumes the original anchor day or the clamped day. Duplicate subscriber
IDs and invalid start dates must not partially mutate records.

### `calendar-harvest-plan`

Window endpoints use an explicit inclusive or half-open convention. A shifted
harvest end that precedes its shifted start is an invalid plan, not an interval
that silently wraps a year.

### `calendar-clinic-followup`

Care plans specify a positive month interval and maximum count/horizon.
Blackouts are caller-supplied dates with stable IDs; define whether a blackout
causes skip, forward adjustment, or explicit unscheduled status.

### `calendar-inventory-expiry`

Shelf-life months use documented end-of-month behavior. Recall state precedence
over active/expiring/expired must be explicit, including a recall exactly on an
otherwise valid expiry boundary.

### `calendar-contract-amendment`

Amendments have stable sequence IDs and effective dates. Specify whether
same-date amendments apply in sequence order and ensure a rejected amendment
leaves the previously valid contract period intact.

### `calendar-vacation-allocation`

Annual balance is an integer day budget with an explicit inclusive-day count.
Closure dates may overlap requested leave; define whether they consume balance,
are excluded, or cause rejection.

### `calendar-maintenance-rotation`

A service interval is a positive count of calendar months, not elapsed seconds.
Define behavior for an original day unavailable in a target month, and whether
a service exactly on the allowed limit remains compliant.

### `calendar-licence-grace`

Specify precedence among active, grace, reinstatement-required, and invalid
states. Reinstatement may use a separate policy duration; equality at each
state boundary requires explicit results.

### `calendar-release-train`

Milestones have stable IDs and intended order. After month shifts and clamping,
collisions must be reported in deterministic order; a rejected shift must not
partially reorder the release train.

### `calendar-lease-portfolio`

Use a stated supported year range and a documented month-bucket endpoint
policy. Invalid/reversed leases and duplicate IDs must remain visible as
diagnostics rather than being silently omitted from the report.

## Materialization Requirements

Every candidate needs a task-specific C++17 public API. Do not expose generic
`add_days`, `add_months`, or `Date::to_string` methods as the assignment.
The starter must expose domain records, policy inputs, structured results, and
explicit invalid-input behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh locked sanitizer build; and
6. shared-denylist and semantic-contamination evidence.

Hidden tests must cover, where applicable:

- ordinary and leap-year February, century, and year-end transitions;
- target months shorter than the anchor day and declared clamp/rollover policy;
- positive/negative or unsupported shifts, checked range limits, and invalid
  civil dates;
- equality at expiry, grace, balance, horizon, and compliance boundaries;
- empty/singleton collections, duplicate IDs, stable ties, and atomic failures;
- overlapping/adjacent spans, blackout/closure policy, and repaired ordering;
- randomized records checked against a small independent proleptic Gregorian
  calendar oracle; and
- a final contamination screen proving the root remains outside every benchmark
  family, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate found to be
a close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.

