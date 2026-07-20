# Clock Arithmetic Curriculum: Decontaminated Capability

Status: v2 local-family remediation contract. This document follows
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with
`FAMILY_NAME=clock-arithmetic`, `FAMILY_TYPE=aider-text-grid-reshaping`, and
the user-authorized hard-rule count of 8–12. It does not claim SFT admission,
an online dataset, training authorization, or benchmark uplift.

The requested legacy path under `aider-text-grid-reshaping` is absent. The
actual ten-root legacy family remains immutable under
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/clock-arithmetic/`. The v2
owner writes only
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/clock-arithmetic/`.
The detailed audit and deterministic remedies are in
`docs/aider-tasks-spec/aider-text-grid-reshaping/clock-arithmetic.md`.

This curriculum develops robust arithmetic over cyclic time: conversion to a
linear minute count, normalization at a cycle boundary, signed offsets,
cross-midnight intervals, fixed-offset local-time conversion, and the
separation of an elapsed duration from a time of day. It deliberately avoids a
standalone clock value-object exercise.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

The official Aider Polyglot C++ `clock` task is a permanent benchmark holdout,
as are every other root in the shared 26-task manifest. Do not reuse its
wording, API, types, constructors, examples, tests, reference implementation,
or model outputs. In particular, do not author a renamed `Clock` class whose
main behavior is construction from hour/minute plus addition, subtraction, and
string formatting.

The v2 roots are designed to be outside the holdout family because each
exposes a domain-specific, multi-input result instead of a general-purpose
time-of-day object. Local verification requires the complete bound 26-root
semantic screen; any near-match is rejected and cannot be waived. Each counted
root must materially differ from every other counted root separately in all
seven hard-rule dimensions, and must differ from `clock` in at least three of
these broader dimensions:

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

## Counted V2 Tasks

The binding family-size range is 8–12. The owner emits exactly ten counted
roots, so count compliance is satisfied only when all ten pass the complete
45-pair seven-dimensional screen and every downstream gate.

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

## Root-Specific Design Contracts

The contracts below are public design constraints. They do not reveal hidden
tests or reference answers. The v2 owner emits the exact public API and
complete deterministic rules in each root's visible instructions.

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

The repository owner is
`src/w8_biayn/integrations/moonlight_clock_arithmetic_aider_tasks.py`; the
focused regression is
`tests/test_moonlight_clock_arithmetic_aider_tasks.py`. Change those sources
and regenerate. Never edit either generated family by hand.

Every candidate needs a distinct C++17 public API. Avoid generic methods such
as `add_minutes`, `subtract_minutes`, `at(hour, minute)`, or `to_string` as the
primary assignment interface. The starter should expose the task's domain
records, policy inputs, result/diagnostic type, and explicit invalid-input
policy.

For each counted root, the owner must emit:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible behavior plus independent private deterministic tests;
5. one strict-compiling topic-specific false substitute that executed tests
   reject;
6. clean normal and fresh ASan/UBSan image-bound builds with positive equal
   discovery; and
7. the complete family, adversarial-control, and benchmark-contamination
   evidence.

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

The production hard-rule evaluator derives these seven dimensions from actual
emitted artifacts: public API, owned state/algorithm, mutation/selection,
invalid/boundary behavior, reference control flow, deterministic oracle, and
topic-specific negative fixture. It compares all 45 unordered pairs
conjunctively. Coherent domain/identifier-renamed, constants/policy-only, and
opposite-end-selection controls must change files, compile, pass their own
consistent tests, and then be rejected as duplicates in all seven dimensions.

Final runtime evidence uses the pinned repository C++ sanity image with Docker
network `none`. The receipt must bind the exact deterministic archive,
independently computed mounted task/control hashes, owner and reference hashes,
image and toolchain identity, commands, two normal and two fresh sanitizer
discoveries per root/control, and executed rejection of every topic-specific
false substitute. This evidence is `docker_sanity`, not a family-designated
`locked_oracle`.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under
the current local task-authoring scope. Dataset handoff is `not_requested`.
A candidate judged to be a close semantic copy of an official benchmark must
be rejected; it cannot be relabelled into this curriculum. Any future dataset
use requires a separate explicitly approved admission contract.

Final local status: `local_family_verified`. The exact ten-root family passes
prompt/role/reference mapping, all 45 seven-dimensional pairs, all three
coherent compiled controls, all 260 holdout comparisons, every strict-compiling
topic negative in both modes, exact owner/mounted hashes, and two equal positive
normal/fresh sanitizer discoveries per root and control. The final family tree
hash is
`sha256:6e28ff3fa9e626f6711c6af2824b1739fdb613e42bbbc15582818f10744c414e`;
the Docker-sanity receipt hash is
`sha256:fb60ffe6b357aaa3ad2ed1723349f7dc4ebfe07bc61b8ffbf28219ffcffdff3a`.
Evidence uses the pinned network-disabled C++ sanity image and is explicitly
`docker_sanity`, not `locked_oracle`. Dataset handoff remains `not_requested`.
