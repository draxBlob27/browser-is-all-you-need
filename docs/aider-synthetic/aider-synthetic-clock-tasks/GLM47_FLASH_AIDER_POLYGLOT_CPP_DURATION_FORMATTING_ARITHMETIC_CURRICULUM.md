# Duration Formatting Arithmetic Curriculum: Decontaminated Capability

Status: remediated local-family curriculum. The immutable ten-root v1 family
remains audit input under `aider-dates-and-clocks`; the owner emits ten v2
replacements only under the user-supplied
`aider-tasks-reverify/aider-text-grid-reshaping/duration-formatting` path. This
does not claim dataset admission, training authorization, or benchmark uplift.

This curriculum teaches conversion of non-negative elapsed quantities into
canonical components, unit selection, rounding policy, pluralization, and
structured presentation. Formatting is the final step of a domain calculation;
the roots do not implement a general-purpose clock or time-of-day type.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

Every official Aider Polyglot C++ root is a permanent holdout. In particular,
do not reuse the `clock` task's wording, API, types, constructors, examples,
tests, reference implementation, or model outputs. Do not create a renamed
clock object whose only observable behavior is normalizing and printing hours
and minutes.

The proposals below are **not yet proven decontaminated**. They deliberately
require a domain record, policy, aggregation, or diagnostic in addition to
duration decomposition. Before admission, run the shared whole-slug benchmark
denylist and semantic-contamination checks; reject and backfill any near-match.
Each surviving root must differ from `clock` in at least three dimensions:
public API/output, input collection or state model, units/rounding policy,
domain operation, and invalid-input/result behavior.

Keep the roots separate from the `gigasecond` future-date and `meetup`
weekday-in-month families. All inputs are caller-supplied integers or typed
records. Do not read the host clock, call a time-zone API, or rely on threads,
filesystem, network, or randomness.

## Online Material Status

Human-readable-duration exercises are available online, but they are useful
only for private concept study or licensed source discovery. They are not a
drop-in SFT inventory. Every root below must be newly authored in C++17 with
independent task text, starter API, reference, examples, and tests, then pass
the repository's provenance, license, oracle, sanitizer, contamination,
split, rendering, and release gates.

## Proposed Decontaminated Tasks

The table below is the historical v1 proposal inventory. Re-verification found
that its generator emitted one generic evaluator/reference/test template for
all ten prompts, so every v1 root has disposition `replace`. The counted v2
inventory is defined below and in
`docs/aider-tasks-spec/aider-text-grid-reshaping/duration-formatting.md`.

| ID | Task | Visible contract | Deliberate separation from `clock` |
|---|---|---|---|
| `duration-parking-receipt` | Parking receipt formatter | Turn a chargeable-minute result and tariff into a receipt with billed blocks, free allowance, and canonical customer-facing duration text. | Formats a billing calculation with tariff diagnostics, not a time-of-day object. |
| `duration-build-summary` | Build pipeline summary | Aggregate named pipeline stages and render total, longest-stage, and failed-stage elapsed summaries under a display-unit policy. | Consumes a stage collection and returns a structured report. |
| `duration-media-chapters` | Media chapter labels | Convert chapter offsets and lengths into monotonic chapter labels, rejecting overlap and non-increasing offsets. | Uses ordered media metadata and validation, not arithmetic on one clock value. |
| `duration-delivery-sla` | Delivery SLA explanation | Compare measured processing and transit durations with separate allowances and format an on-time/late explanation. | Combines multiple budgets and a typed compliance outcome. |
| `duration-sports-splits` | Race split recap | Summarize lap durations, calculate fastest/slowest spread, and format a ranked recap with configured precision. | Aggregates a sequence with ranking and precision rules. |
| `duration-battery-forecast` | Battery reserve forecast | Decompose remaining operating seconds into a device-specific reserve message, accounting for a non-displayable safety reserve. | Separates usable and reserved capacity under safety policy. |
| `duration-maintenance-window` | Maintenance window report | Format planned, consumed, paused, and remaining maintenance budget while detecting an overrun. | Works on a duration ledger with pause accounting and status. |
| `duration-study-ledger` | Study ledger digest | Group categorized focus records and format per-category totals plus an unassigned-duration warning. | Groups a record set and exposes allocation diagnostics. |
| `duration-rescue-air` | Rescue air plan | Convert oxygen consumption data into reserve, usable duration, and turn-back guidance using conservative rounding. | Requires rate calculation, safety margin, and directional rounding. |
| `duration-archive-retention` | Archive retention notice | Render retention age and purge countdown from policy tiers, including `due now` and `indefinite` result forms. | Selects policy-specific phrases from a retention record, not clock formatting. |

## Root-Specific Design Notes

These constraints guide later authors; they are not hidden tests or reference
answers. Independently author all names, types, examples, and algorithms.

## Counted v2 replacement inventory

The user-authorized hard-rule range is 8–12; the owner emits exactly ten roots
and must prove all 45 unordered pairs materially different in each of the seven
mandatory dimensions separately.

| Replacement | Core logic | Topic-specific rejected substitute |
| --- | --- | --- |
| `parking-block-receipt` | checked ceiling blocks then checked charge | floor division |
| `pipeline-stage-digest` | ordered validation, total, strict maximum, stable failures | latest-wins tie |
| `chapter-timeline-labels` | complete partition validation then integer labels | accepting gaps |
| `split-budget-sla` | independent excesses and four-state status lattice | combined-total SLA |
| `ranked-lap-recap` | checked extrema and stable fastest-first index rank | descending rank |
| `reserve-discharge-forecast` | aggregate ceiling rate then floor duration | truncated rate |
| `maintenance-event-ledger` | strict begin/pause/resume/finish state machine | charging paused time as active |
| `categorized-focus-digest` | configured lookup buckets plus unassigned total | dropping unknowns |
| `turnback-air-plan` | per-diver ceiling, reserve ceiling, turn-back minimum | aggregate truncation |
| `tiered-retention-notice` | validated greatest-qualified tier and state precedence | first-qualified tier |

### `duration-parking-receipt`

Specify block size, partial-block rounding, free allowance, and currency-free
integer charge units. A zero-duration visit and a visit exactly at an allowance
or block boundary must have unambiguous receipt text.

### `duration-build-summary`

Stage identifiers are stable and unique. Decide whether failed stages count in
the total and define deterministic longest-stage ties; an empty pipeline must
return a report rather than attempting an invalid maximum.

### `duration-media-chapters`

Use non-negative offsets and lengths. The output format must preserve the
configured precision without floating-point drift, and a final chapter may not
extend beyond the declared media length.

### `duration-delivery-sla`

Keep processing and transit allowances separate. Define whether equality with
the combined allowance is on time and ensure a negative/invalid input cannot
produce a misleading late-duration message.

### `duration-sports-splits`

Each lap duration is positive. Define rank ties, precision rounding mode, and
whether the recap prints a total even when a partial race is explicitly marked
incomplete.

### `duration-battery-forecast`

Use an integer consumption rate and checked division. The safety reserve is
not reportable as available time; define the exact message at zero usable
seconds and for a rate that makes no whole display unit available.

### `duration-maintenance-window`

Treat active and paused entries as different ledger records. Invalid state
order, such as resume without pause, must preserve the previous valid total and
return a diagnostic.

### `duration-study-ledger`

Categories have stable display order. A record with an unknown category is
accounted for in an explicit unassigned bucket rather than silently dropped.

### `duration-rescue-air`

Specify conservative rounding toward the earlier turn-back deadline. Reject
zero or negative consumption rates and distinguish impossible reserve plans
from a plan with zero usable duration.

### `duration-archive-retention`

Use explicit tier boundaries and remaining elapsed units, never calendar dates.
Define precedence between `indefinite`, `due now`, and ordinary countdown
messages, including equality at a purge boundary.

## Materialization Requirements

Every candidate needs a task-specific C++17 public API. Do not expose generic
`hours`, `minutes`, `seconds`, or `to_string` methods as the assignment.
The starter must expose domain records, policy inputs, a structured result, and
explicit invalid-input behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh locked sanitizer build; and
6. shared-denylist and semantic-contamination evidence.

Hidden tests must cover, where applicable:

- zero, one-unit, and large durations with checked conversion arithmetic;
- exact component boundaries such as 60 seconds, 60 minutes, and 24 hours;
- pluralization, omitted zero components, and configured unit/rounding policy;
- equality at allowance, tariff, reserve, and deadline thresholds;
- empty/singleton record collections, stable ties, and invalid records without
  partial state mutation;
- aggregates whose components must recombine to the original total;
- randomized integer-duration ledgers checked against a small independent
  formatter/oracle; and
- a final contamination screen proving the root remains outside all benchmark
  families, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A close semantic copy
of an official benchmark must be rejected and backfilled; it cannot be
relabelled into this curriculum.
