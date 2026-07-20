# Cross-Midnight Intervals Arithmetic Curriculum: Decontaminated Capability

Status: remediation owner for eight local v2 replacement roots. This document
does not claim that they are admitted SFT roots or available as an online
dataset.

The v1 tree remains immutable at
`.w8-biayn/data/aider-tasks/aider-dates-and-clocks/cross-midnight-intervals/`.
The user-selected remediation input names
`FAMILY_TYPE=aider-text-grid-reshaping`, although no corresponding legacy tree
exists under that type. The audit therefore binds the historical owner-owned
date/clock tree as its preserved input and writes fresh v2 artifacts only to
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/cross-midnight-intervals/`.
That mismatch is recorded in every remedy record; it is not hidden by moving
or modifying legacy files.

The user-authorized hard count is 8–12. The owner emits exactly eight counted
roots and requires all 28 unordered pairs to differ separately in public API,
owned state/algorithm, mutation/selection rules, invalid/boundary behavior,
reference control flow, deterministic oracle, and topic-negative fixture.
Domain/identifier renames, constants/policy-only changes, and opposite-end
selection changes are coherent compiled controls, not counted roots.

This curriculum develops arithmetic for bounded daily intervals that can cross
a day boundary: half-open endpoint policy, duration, containment, overlap,
union, allocation, and boundary diagnostics. It does not teach a standalone
time-of-day value object or generic clock formatting.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

Every official Aider Polyglot C++ root is a permanent holdout. In particular,
do not reuse the `clock` task's wording, API, types, constructors, examples,
tests, reference implementation, or model outputs. Do not make a renamed
`Clock` class that merely normalizes hour/minute fields or adds/subtracts
offsets.

The proposals below are **not yet proven decontaminated**. They are designed
around typed intervals, collection-level policy, and domain diagnostics rather
than a single clock value. Before admission, run the shared whole-slug benchmark
denylist and semantic-contamination checks; reject and backfill every near
match. Each surviving root must differ from `clock` in at least three
dimensions: public API/output, interval/collection model, endpoint or resource
policy, query/diagnostic behavior, and invalid-input treatment.

Keep roots separate from the `gigasecond` future-date and `meetup`
weekday-in-month families. All behavior is deterministic from supplied local-day
minute values: no host clock, time-zone data, daylight saving, filesystem,
network, threads, or randomness.

## Online Material Status

Overnight schedule and interval exercises are useful only for private concept
study or licensed source discovery. They are not a drop-in SFT inventory. Each
candidate must be newly authored in C++17 with independent task text, starter
API, reference, examples, and tests, then pass provenance, license, oracle,
sanitizer, contamination, split, rendering, and release gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from `clock` |
|---|---|---|---|
| `midnight-parking-rate` | Overnight parking rate | Price a visit against peak and off-peak bands that may wrap midnight, returning band-by-band charged minutes. | Splits one visit against a tariff collection and produces billing evidence. |
| `midnight-security-patrol` | Security patrol coverage | Merge guard patrol intervals and report uncovered overnight checkpoint windows. | Uses interval union and missing-coverage diagnostics. |
| `midnight-dock-allocation` | Freight dock allocation | Accept or reject overnight dock reservations by half-open overlap rules and return the first conflicting booking. | Maintains mutable resource bookings with conflict identity. |
| `midnight-sleep-tracker` | Sleep session analyzer | Classify a sleep interval into pre-midnight, post-midnight, and interruption minutes under a supplied wake log. | Intersects a session with a disruption record set. |
| `midnight-radio-silence` | Radio silence verifier | Check whether transmissions violate protected quiet windows, including a window that wraps the day boundary. | Evaluates event points against policy intervals and violation details. |
| `midnight-bakery-oven` | Bakery oven schedule | Assign bake batches to a limited oven count across an overnight production window and report capacity conflicts. | Combines interval arithmetic with bounded-resource allocation. |
| `midnight-transit-pass` | Transit pass validator | Determine whether a ride interval remains covered by a pass with an overnight validity window and grace policy. | Applies entitlement and grace semantics to a trip interval. |
| `midnight-hospital-handoff` | Hospital handoff audit | Measure overlap and gap between consecutive overnight care shifts and flag unsafe handoff gaps. | Uses ordered shift collections plus safety thresholds. |
| `midnight-noise-budget` | Neighborhood noise budget | Accumulate noisy-operation minutes inside protected overnight periods and report the first policy breach. | Intersects many operation intervals with policy bands and a budget. |
| `midnight-delivery-curfew` | Delivery curfew planner | Filter candidate delivery routes by curfew intersection and return the earliest legal dispatch alternative. | Searches a route collection under legality and tie-break rules. |

## Deterministic V2 Dispositions

The legacy generator materialized all ten proposals through one generic
`Span` class template, one result shape, the same overlap/sort loop, and the
same tests after class/method noun substitution. Consequently every legacy root
has `primary_core_objective: not_achieved`; eight receive independent
replacements and two semantically overlapping candidates are rejected. None is
retained through a rename-only repair.

| Legacy audit root | V2 replacement | Required mechanism |
| --- | --- | --- |
| `midnight-parking-rate` | `overnight-parking-ledger` | boundary-event tariff sweep |
| `midnight-security-patrol` | `patrol-gap-union` | clipped interval-union complement |
| `midnight-dock-allocation` | `dock-booking-calendar` | mutable per-resource ordered calendar |
| `midnight-sleep-tracker` | `sleep-interruption-ledger` | **reject:** overlaps retained union/complement mechanism |
| `midnight-radio-silence` | `quiet-window-violations` | stable point-membership selection |
| `midnight-bakery-oven` | `oven-capacity-scheduler` | two-heap interval partitioning |
| `midnight-transit-pass` | `transit-entitlement-audit` | **reject:** overlaps retained interval-feasibility mechanism |
| `midnight-hospital-handoff` | `handoff-continuity-audit` | adjacent continuity-state accumulation |
| `midnight-noise-budget` | `noise-budget-breach` | incremental protected-minute bitmap |
| `midnight-delivery-curfew` | `curfew-dispatch-selector` | ordered candidate feasibility search |

The normative per-root APIs, behaviors, invariants, negative fixtures, role
maps, oracle commands, and acceptance gates are frozen before implementation
under the reverify root's `.state/remedy/` directory. The checked-in audit is
`docs/aider-tasks-spec/aider-text-grid-reshaping/cross-midnight-intervals.md`.

The corrected local evidence records exactly eight materialized roots, 28
passing seven-dimension pair decisions, two absent rejected roots, 208 passing
comparisons against all 26 official C++ holdouts, eight passing normal/fresh
sanitizer references, eight rejected compiled topic negatives, and three
compiled/tested/rejected coherent controls. The former ten-root receipt was
invalidated because unequal normalized digests did not establish material
diversity; a subsequent receipt with empty control hashes was also invalidated.
The final network-disabled Docker receipt binds the eight root hashes, three
distinct nonempty control hashes, and an aggregate owner hash covering the
materializer, case inventory, and production hard-rule evaluator. Its evidence
class is `docker_sanity`, `locked_oracle` is false, the family returns to
`local_family_verified`, and dataset handoff remains `not_requested`.

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Names,
types, examples, and algorithms must be independently authored during
materialization.

### `midnight-parking-rate`

Specify a half-open interval convention and handling for a zero-length visit.
Bands may touch but must not overlap; a visit exactly on a boundary needs an
unambiguous charge allocation.

### `midnight-security-patrol`

Checkpoints are a bounded local-day observation window, not dates. Define
whether touching patrols merge and return uncovered segments in deterministic
chronological order after unwrapping the selected overnight window.

### `midnight-dock-allocation`

Reservation identifiers are stable. Reject invalid/reversed records before
testing overlap, and ensure an unsuccessful insertion does not mutate the
reservation set.

### `midnight-sleep-tracker`

A sleep session may cross midnight once under the stated domain bound. Wake-log
events must be contained in the session and deduplicated by stable event ID;
define whether their own durations may overlap.

### `midnight-radio-silence`

Transmission points and intervals are distinct inputs. State whether endpoints
of a protected half-open silence window count as violations and return the
first violating transmission under a documented input-order tie policy.

### `midnight-bakery-oven`

Each batch has a positive duration and stable identifier. Define the exact
capacity rule at touching endpoints and choose deterministic oven assignment
when several ovens become available together.

### `midnight-transit-pass`

The pass and ride both use explicit interval endpoints. Define whether a grace
period extends the pass end only, whether an exact endpoint is covered, and how
a trip spanning more than one daily cycle is rejected.

### `midnight-hospital-handoff`

Shift records are ordered by the caller after validation. Compute overlap and
gap without treating an overnight end as earlier than its start; equality at a
minimum handoff overlap needs an explicit safety policy.

### `midnight-noise-budget`

Operations may overlap each other, but their intersection with protected
periods must follow a documented union-or-per-operation charging rule. A breach
must identify the causal operation deterministically.

### `midnight-delivery-curfew`

Candidate routes include a stable route ID and proposed interval. Define route
ordering for equally early legal alternatives and whether a zero-duration route
is a valid delivery or an invalid input.

## Materialization Requirements

Every candidate needs a task-specific C++17 public API. Do not expose generic
`add_minutes`, `subtract_minutes`, `hour`, `minute`, or `to_string`
methods as the assignment. The starter must expose domain records, endpoint
policy, structured results, and explicit invalid-input behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh locked sanitizer build; and
6. shared-denylist and semantic-contamination evidence.

Hidden tests must cover, where applicable:

- non-wrapping, wrapping, zero-length, and full-window intervals;
- endpoints exactly at midnight and at declared half-open/closed boundaries;
- overlap, containment, adjacency, disjointness, and union across midnight;
- empty/singleton collections, stable ties, and no-state-mutation failures;
- conflicting records, capacity limits, grace thresholds, and repeated IDs;
- large randomized interval traces checked against a small independent linear
  unwrapped-minute oracle; and
- a final contamination screen proving the root remains outside every benchmark
  family, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate found to be
a close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.
