# Leap-Year Rule Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum applies the Gregorian leap-year rule within domain policies:
divisible-by-4 qualification, century exclusion, divisible-by-400 restoration,
and resulting February/day-capacity behavior. It intentionally avoids a bare
boolean leap-year kata and does not perform general future-date arithmetic.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

The full official Aider Polyglot C++ holdout manifest is permanently excluded.
In particular, do not reuse `gigasecond` or `clock` wording, API, types,
examples, tests, references, or model outputs. Do not create a renamed
`is_leap_year(year)` exercise or a near-copy that adds a fixed large date
offset.

The proposals below are **not yet proven decontaminated**. They embed the rule
in domain-specific validation, allocation, reporting, or scheduling contracts.
Before admission, run the shared whole-slug benchmark denylist and semantic
contamination checks; reject and backfill every near-match. Each surviving root
must materially differ from benchmark families in at least three dimensions:
public API/output, data collection or state model, domain policy, result or
diagnostic type, and invalid-input behavior.

Keep roots separate from the `gigasecond` future-date and `meetup`
weekday-in-month families. Inputs must be caller supplied and deterministic:
no host clock, calendar/time-zone library dependence, filesystem/network,
threads, or randomness.

## Online Material Status

Leap-year examples are useful only for private concept study or licensed source
discovery. They are not a drop-in SFT inventory. Each candidate must be newly
authored in C++17 with independent task text, starter API, reference, examples,
and tests, then pass provenance, license, oracle, sanitizer, contamination,
split, rendering, and release gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from holdouts |
|---|---|---|---|
| `leap-february-inventory` | February inventory planner | Validate daily stock targets for February and return capacity, missing-day, and over-capacity diagnostics. | Uses a month inventory record and validation report, not a date-offset API. |
| `leap-payroll-accrual` | Payroll accrual ledger | Allocate a February daily benefit across employee records and reconcile the annual leap-day accrual policy. | Aggregates employee policy records with monetary-unit totals. |
| `leap-weather-archive` | Weather archive completeness | Audit February observation IDs for duplicate, missing, and invalid day slots under the record's year. | Processes a data collection and returns completeness diagnostics. |
| `leap-facility-booking` | Facility booking validator | Admit or reject February maintenance bookings, including leap-day requests, under capacity and blackout rules. | Combines calendar validation with mutable booking conflict policy. |
| `leap-publication-cycle` | Publication cycle planner | Produce the eligible February issue slots for a supplied publication cadence and explain a skipped or added leap-day slot. | Applies cadence and exception policy to a schedule result. |

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Names,
types, examples, and algorithms must be independently authored during
materialization.

### `leap-february-inventory`

Inventory slots are day-numbered records, not parsed dates. Define the valid
year range and whether a missing target is distinct from an explicit zero
target. Day 29 must be rejected in a common year without mutating the report.

### `leap-payroll-accrual`

Use integer benefit units and an explicit policy for leap-day allocation across
employees. Define deterministic remainder distribution and whether inactive
employees receive any portion of the additional day.

### `leap-weather-archive`

Observation IDs and day slots are stable. A duplicate must be reported without
hiding a missing slot, and out-of-range days must be retained as diagnostics
rather than silently discarded.

### `leap-facility-booking`

Bookings have stable IDs, a February day, and a resource demand. A failed
leap-day or capacity validation must not insert the booking; equal capacity
must have an explicit accept/reject rule.

### `leap-publication-cycle`

Cadence is a positive day interval anchored within February. Define whether
the final day is included, how a cadence that would otherwise land on day 29
behaves in a common year, and the stable ordering of explanations.

## Materialization Requirements

Every candidate needs a task-specific C++17 public API. Do not expose a bare
`is_leap_year` function as the assignment. The starter must expose domain
records, policy inputs, structured results, and explicit invalid-input
behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh locked sanitizer build; and
6. shared-denylist and semantic-contamination evidence.

Hidden tests must cover, where applicable:

- years divisible by 4, 100, and 400, plus ordinary common years;
- February days 1, 28, 29, and out-of-range day numbers;
- zero, exact-capacity, and over-capacity allocations;
- empty/singleton collections, duplicates, stable ordering, and atomic failure;
- leap/common-year transitions in the task-specific policy;
- randomized year/record inputs checked against a small independent Gregorian
  rule and domain oracle; and
- a final contamination screen proving the root remains outside every benchmark
  family, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate found to be
a close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.

