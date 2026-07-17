# Clock Arithmetic Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum develops robust arithmetic over cyclic time: conversion to a
linear minute count, normalization at a cycle boundary, signed offsets,
cross-midnight intervals, fixed-offset local-time conversion, and the
separation of an elapsed duration from a time of day. It deliberately avoids a
standalone clock value-object exercise.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

The official Aider Polyglot C++ `clock` task is a permanent benchmark holdout,
as are every other root in the shared 26-task manifest. Do not reuse its
wording, API, types, constructors, examples, tests, reference implementation,
or model outputs. In particular, do not author a renamed `Clock` class whose
main behavior is construction from hour/minute plus addition, subtraction, and
string formatting.

The proposals below are **not yet proven decontaminated**. They are designed
to be outside the holdout family because each exposes a domain-specific,
multi-input result instead of a general-purpose time-of-day object. Before
admission, the normal whole-slug denylist and semantic contamination checks
must reject any near-match and require a replacement. Each surviving root must
materially differ from `clock` in at least three dimensions:

1. public API and output shape;
2. state or collection model;
3. required operation beyond simple add/subtract/format;
4. boundary policy, cycle length, or fixed-offset rule; and
5. domain-specific invalid-input and diagnostic behavior.

Keep the proposed roots separate from the `gigasecond` future-date family and
the `meetup` weekday-in-month family as well. No task may depend on the host
clock, time zone database, daylight-saving rules, filesystem, network, or
randomness.

## Online Material Status

Clock and timetable exercises are widely available online, but they are useful
only for private concept study or licensed source discovery. They are not a
drop-in SFT inventory. Each resulting root must be newly authored in C++17,
with independent task text, starter API, reference, examples, and tests, then
pass provenance, license, oracle, sanitizer, contamination, split, rendering,
and release gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from `clock` |
|---|---|---|---|
| `time-parking-grace-audit` | Parking grace audit | Given arrival/departure records and a grace allowance, return chargeable minutes plus a `crossed_midnight` diagnostic. | Computes an interval and billing result from two readings; exposes no mutable clock object. |
| `time-rail-transfer-checker` | Rail transfer checker | Evaluate a passenger itinerary against minimum transfer rules and report the first missed connection or total layover. | Operates on a sequence of events and a typed feasibility result, not a single normalized time. |
| `time-medication-window` | Medication window | Determine whether dose events satisfy a repeating allowed window and minimum spacing rule. | Combines cyclic containment, event history, and policy violations. |
| `time-overnight-roster` | Overnight roster | Calculate paid, night-premium, and break minutes for shifts that may cross midnight. | Splits intervals against premium bands and produces an aggregate payroll record. |
| `time-irrigation-cycle` | Irrigation cycle planner | From a cycle anchor, duration, and blackout intervals, find the next permitted run or report none within one cycle. | Uses a configurable cycle and interval exclusion/search rather than a 24-hour value type. |
| `time-backup-cutover` | Backup cutover verifier | Apply dated-in-order cutover events to a maintenance window and report service minutes, outage minutes, and invalid transitions. | Is an event-state machine with transition diagnostics and duration aggregation. |
| `time-briefing-offset-board` | Briefing offset board | Convert an announced reference minute to several fixed-offset locations and label each as previous, same, or next local day. | Performs one-to-many fixed-offset conversion with day-relative labels, never system time zones. |
| `time-satellite-phase-log` | Satellite phase log | Normalize signed phase advances on a configurable orbital period and find the shortest signed correction to a target phase. | Uses arbitrary-period modular arithmetic and minimum-distance tie policy, not clock formatting. |
| `time-school-bell-repair` | School bell repair | Apply ordered delays, cancellations, and inserted breaks to a bell schedule; return the repaired ordered sequence and conflict diagnostics. | Mutates a collection of scheduled events under ordering and collision rules. |
| `time-oven-program` | Oven program sequencer | Advance a multi-stage cooking program through elapsed-minute updates, pausing at stage boundaries and reporting remaining stage/program time. | Models elapsed duration and staged state, explicitly distinct from time of day. |

## Root-Specific Design Notes

The contracts below are constraints for future authors, not hidden tests or
reference answers. Names, types, examples, and exact algorithms must be
authored afresh during materialization.

### `time-parking-grace-audit`

Use validated local-day minute readings and an explicit `departure_is_next_day`
flag rather than parsing display strings. Define whether equality at the grace
limit is free. Reject malformed readings without returning a partial bill.

### `time-rail-transfer-checker`

Represent each leg by arrival/departure minute and service identifier. Include
same-service continuation, an itinerary whose first leg is invalid, and a
transfer that crosses midnight. Specify whether a layover exactly equal to the
minimum is valid.

### `time-medication-window`

Make the allowed interval half-open or closed explicitly, including a window
that crosses midnight. Separate a missed window from a too-soon dose and make
the returned violation identify the relevant event index.

### `time-overnight-roster`

Use a documented half-open shift convention. Breaks must be contained in a
shift, may not overlap, and must be subtracted before premium-band accounting.
Define whether a shift exactly on a premium boundary receives premium time.

### `time-irrigation-cycle`

Use a caller-supplied positive cycle length, so the root cannot collapse into
a 24-hour clock exercise. Blackouts may wrap the cycle boundary; overlapping
blackouts must be canonicalized before the search.

### `time-backup-cutover`

Specify the legal event-state graph, for example `serving -> draining ->
offline -> restoring -> serving`. Equal-minute events need deterministic input
order semantics. An invalid transition must name its event without corrupting
the previously valid state.

### `time-briefing-offset-board`

Offsets are signed whole minutes within a stated bound, supplied by the caller;
do not consult a system time-zone database. The result preserves each location
label, normalized local minute, and relative-day marker.

### `time-satellite-phase-log`

Require an explicit policy for exactly half-period corrections on even periods.
Large signed advances must normalize without overflow and repeated advances
must agree with their summed equivalent where that sum is representable.

### `time-school-bell-repair`

Schedule entries have stable identifiers. Define collision behavior after
delays and the cancellation semantics for an unknown or already cancelled
identifier. The output must remain deterministically ordered by repaired
minute and a documented tie key.

### `time-oven-program`

Stages have positive durations and named completion actions. A single advance
may cross several stages; an advance after completion must have a specified
no-op or error result. Do not model this as an absolute wall-clock time.

## Materialization Requirements

Every candidate needs a distinct C++17 public API. Avoid generic methods such
as `add_minutes`, `subtract_minutes`, `at(hour, minute)`, or `to_string` as the
primary assignment interface. The starter should expose the task's domain
records, policy inputs, result/diagnostic type, and explicit invalid-input
policy.

For each proposed root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples plus hidden Catch tests;
5. normal build and a fresh locked sanitizer build; and
6. the required benchmark and semantic-contamination evidence.

Hidden tests must cover, where applicable:

- exact cycle boundaries, negative offsets, and offsets larger than one cycle;
- crossings in both directions over the cycle boundary;
- equality rules at grace, transfer, interval, and stage boundaries;
- empty/singleton collections, stable event ordering, and no-state-mutation
  failures;
- overlapping, adjacent, and boundary-wrapping policy intervals;
- large-but-valid values with checked arithmetic and deterministic diagnostics;
- randomized traces checked against a small independent linear-minute oracle;
- explicit proof that the task contract has not become a close semantic copy of
  any benchmark holdout, especially `clock`, `gigasecond`, or `meetup`.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate judged to
be a close semantic copy of the official `clock` benchmark must be rejected
and backfilled; it cannot be relabelled into this curriculum.
