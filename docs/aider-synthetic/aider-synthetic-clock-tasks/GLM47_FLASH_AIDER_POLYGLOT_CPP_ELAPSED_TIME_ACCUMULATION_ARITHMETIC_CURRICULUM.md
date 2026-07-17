# Elapsed-Time Accumulation Arithmetic Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum teaches safe accumulation of elapsed durations: checked addition,
overlap policy, deduplication, pause exclusion, unit conversion, bounded
budgets, and deterministic aggregation. It distinguishes elapsed work from a
time of day and does not propose a general-purpose clock value object.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

All official Aider Polyglot C++ roots are permanent holdouts. In particular,
do not reuse the `clock` task's wording, API, types, constructors, examples,
tests, reference implementation, or model outputs. Do not disguise a simple
hour/minute clock exercise as an accumulator with a new name.

The proposals below are **not yet proven decontaminated**. They are designed
around domain records and aggregation policies rather than a single normalized
clock value. Before admission, run the shared whole-slug benchmark denylist and
semantic-contamination checks; reject and backfill any near-match. Each
surviving root must differ from `clock` in at least three dimensions: public
API/output, collection or state model, aggregation/overlap rule, budget or
policy behavior, and invalid-input diagnostic.

Keep these roots separate from the `gigasecond` future-date and `meetup`
weekday-in-month families. All inputs must be caller supplied and deterministic:
no host clock, time-zone lookup, filesystem/network access, threads, or
randomness.

## Online Material Status

Time-tracking and duration-summing exercises are useful only for private
concept study or licensed source discovery. They are not a drop-in SFT
inventory. Every candidate must be newly authored in C++17 with independent
task text, starter API, reference, examples, and tests, then pass provenance,
license, oracle, sanitizer, contamination, split, rendering, and release
gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from `clock` |
|---|---|---|---|
| `elapsed-consulting-invoice` | Consulting invoice ledger | Aggregate approved work entries by client, exclude breaks, apply a daily cap, and return billable versus capped minutes. | Uses a multi-client ledger and cap policy, not time-of-day mutation. |
| `elapsed-machine-utilization` | Machine utilization audit | Combine running, idle, setup, and fault intervals into utilization totals while rejecting overlapping state records. | Classifies interval records and validates coverage conflicts. |
| `elapsed-reading-challenge` | Reading challenge tracker | Add signed corrections to book-session durations, enforce a non-negative total, and report progress toward a goal. | Uses corrections and a goal state with underflow diagnostics. |
| `elapsed-battery-test-log` | Battery test log | Sum device test phases, omit aborted phases under a declared policy, and report the longest contributing phase. | Aggregates typed phases and contribution status. |
| `elapsed-freelance-breaks` | Freelance break reconciler | Reconcile active and break events into paid minutes, identifying unmatched starts/stops and duplicate closes. | Requires event-pair state reconciliation, not a duration formatter. |
| `elapsed-training-load` | Training-load accumulator | Combine exercise sets with intensity weights and rest exclusions into a bounded training-load score and duration summary. | Adds weighted domain scoring and record filtering. |
| `elapsed-network-uptime` | Network uptime ledger | Merge adjacent outage reports by service, detect conflicting reports, and calculate covered uptime within an observation budget. | Performs interval union and service-level diagnostics. |
| `elapsed-lab-equipment-booking` | Lab equipment booking audit | Accumulate approved reservation use, charge overrun minutes, and return the first booking that exceeds an allocation. | Uses resource allocation and first-failure reporting. |
| `elapsed-podcast-production` | Podcast production digest | Total recording, editing, and review passes; deduplicate retried export records by immutable job ID. | Combines categories with idempotent record handling. |
| `elapsed-incident-response` | Incident response timeline | Accumulate response phases across incidents, separate active mitigation from waiting, and flag a breached response budget. | Produces multi-incident operational aggregates and policy status. |

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Names,
types, examples, and algorithms must be independently authored during
materialization.

### `elapsed-consulting-invoice`

Entries include a stable identifier, client, day bucket, and elapsed minutes.
Define whether a daily cap uses entry order or proportional allocation; rejected
or duplicate entries must not partially change invoice totals.

### `elapsed-machine-utilization`

Each state interval uses a documented half-open endpoint convention. Adjacent
same-state records may merge, but overlapping different-state records must name
the conflict without producing a misleading utilization percentage.

### `elapsed-reading-challenge`

A correction references a prior session by stable ID. Define whether correction
magnitude may exceed that session and whether an aggregate that would fall below
zero is rejected atomically or clamped with a diagnostic.

### `elapsed-battery-test-log`

Define the contribution rule for aborted, retried, and failed phases. Longest
phase ties must be stable, and total arithmetic must be checked before any unit
conversion or display formatting.

### `elapsed-freelance-breaks`

Specify legal active/break event transitions per worker. Equal-position events
need deterministic input-order behavior; unmatched events must not create
negative paid duration.

### `elapsed-training-load`

Duration and intensity are separate typed fields. Define rounding and cap order,
and reject invalid intensity values rather than silently treating them as zero.

### `elapsed-network-uptime`

The observation budget is caller supplied, not a civil day. Define treatment of
outages outside it, touching endpoints, and duplicate reports for the same
service with unequal identifiers.

### `elapsed-lab-equipment-booking`

Reservations have a unique booking ID and approved allocation. State whether
an exact allocation match is valid and whether cancelled bookings contribute
zero use or remain visible in diagnostics.

### `elapsed-podcast-production`

Retries share an immutable job ID with an attempt sequence. Define which
attempt contributes and how an out-of-order retry is rejected or superseded.

### `elapsed-incident-response`

Each incident has an ordered phase log. Waiting time must remain distinct from
active mitigation, and a budget breach must report the first causal phase under
a documented tie rule.

## Materialization Requirements

Every candidate needs a task-specific C++17 public API. Do not expose generic
`add_minutes`, `subtract_minutes`, `hours`, or `to_string` methods as the
assignment. The starter must expose domain records, policy inputs, structured
results, and explicit invalid-input behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh locked sanitizer build; and
6. shared-denylist and semantic-contamination evidence.

Hidden tests must cover, where applicable:

- empty and singleton ledgers, zero durations, and checked large totals;
- addition boundaries, unit conversions, and no signed/unsigned underflow;
- duplicate IDs, stable tie handling, and rejected-record no-state mutation;
- overlap, adjacency, gaps, and explicit half-open/closed endpoint policy;
- pauses, corrections, retries, cancellations, and cap/budget boundaries;
- randomized record sequences checked against a small independent integer
  accumulator or interval-union oracle; and
- a final contamination screen proving the root remains outside every benchmark
  family, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate found to be
a close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.

