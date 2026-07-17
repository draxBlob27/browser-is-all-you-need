# Countdown Timers Arithmetic Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum develops arithmetic over non-negative elapsed durations:
checked decrement, saturation at zero, pause/resume accounting, multiple
deadline ordering, duration decomposition, and exactly-once expiry effects. It
teaches timer state machines without treating an elapsed duration as a clock of
day.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

The full official Aider Polyglot C++ holdout manifest is excluded. In
particular, `clock` is a permanent holdout: do not reuse its wording, API,
types, constructors, examples, tests, reference implementation, or model
outputs. Do not turn a generic decrementing duration object into a renamed
`Clock` exercise by adding only `tick`, `add`, and formatting methods.

The proposals below are **not yet proven decontaminated**. They are designed to
avoid the `clock` family by making countdown arithmetic one component of a
domain-specific state machine, collection, or diagnostic result. Before
admission, run the shared whole-slug benchmark denylist and semantic
contamination checks. Reject and backfill any close match. A surviving root
must differ from `clock` in at least three dimensions: public API/output,
state or collection model, event/expiry policy, boundary/rounding rule, and
domain-specific invalid-input behavior.

Keep these roots separate from the `gigasecond` future-date family and the
`meetup` weekday-in-month family. All behavior must be deterministic from
caller-supplied elapsed values: do not read a host clock, use timers/threads,
consult time zones, access the filesystem/network, or depend on randomness.

## Online Material Status

Countdown tutorials and timer exercises are useful only for private concept
study or licensed source discovery. They are not a drop-in SFT inventory. Each
candidate must be newly authored in C++17, with independent specification,
starter API, reference, examples, and tests; it must then pass provenance,
license, oracle, sanitizer, contamination, split, rendering, and release
gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from `clock` |
|---|---|---|---|
| `timer-launch-hold` | Launch hold controller | Advance a launch countdown through hold, resume, and abort events; return remaining time and transition diagnostics. | A guarded state machine with legal transitions and abort semantics, not a time-of-day value. |
| `timer-auction-extension` | Auction extension monitor | Process bid events and extend only deadlines inside an anti-sniping window, subject to a total-extension cap. | Uses ordered event history, conditional extension, and a policy result. |
| `timer-parking-credit` | Parking credit meter | Consume prepaid parking credit across elapsed updates, top-ups, and a maximum balance; report exact expiry and rejected top-ups. | Models a bounded balance with billing events, not display-time arithmetic. |
| `timer-chess-round` | Chess round adjudicator | Apply legal alternating moves with per-player remaining budgets and increments; identify flag fall or invalid move order. | Maintains two coupled budgets plus turn ownership and increment policy. |
| `timer-incubator-checkpoints` | Incubator checkpoint tracker | Advance an incubation run and emit each checkpoint crossed exactly once, including several crossed by one update. | Requires milestone stream semantics and exactly-once delivery. |
| `timer-evacuation-drill` | Evacuation drill scorecard | Score staged evacuation deadlines with grace bands and record the first stage that fails. | Aggregates multiple deadlines into a typed assessment rather than formatting duration. |
| `timer-game-cooldown-registry` | Game cooldown registry | Register named abilities, advance all cooldowns, reset selected abilities, and list abilities newly ready in stable order. | Operates on a keyed collection with simultaneous advancement and ready-event deltas. |
| `timer-oven-safety-lock` | Oven safety lock | Decrement a child-safety lock, allow a bounded relock credit, and distinguish active, expired, and permanently disabled states. | Encodes capped renewal and irreversible state behavior. |
| `timer-build-lease` | Build-agent lease manager | Apply elapsed time and heartbeat renewals to worker leases; return expired worker IDs and reject stale renewals. | Uses multiple leases, identity checks, and expiry batches. |
| `timer-study-session-budget` | Study session budget | Allocate a fixed focus budget over ordered activities, pauses, and mandatory breaks; report unused time and policy violations. | Combines a duration ledger with activity sequencing and break constraints. |

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Types,
examples, names, and algorithms must be independently authored during
materialization.

### `timer-launch-hold`

Define a finite legal transition graph, such as armed, holding, counting,
aborted, and launched. Advancing by zero must be specified, and an update that
reaches zero must launch once rather than permitting underflow or repeated
launch events.

### `timer-auction-extension`

Use caller-supplied elapsed event positions, not civil dates. Define whether a
bid exactly on the extension threshold qualifies, how equal-position bids are
ordered, and whether a cap applies to elapsed extension, extension count, or
both.

### `timer-parking-credit`

Specify a positive unit rate and cap. An elapsed update larger than the
remaining credit must saturate cleanly and report the exact unpaid remainder;
a rejected top-up must not mutate balance or expiry evidence.

### `timer-chess-round`

Time advances only for the active player. Define whether a move landing
exactly at zero is legal, whether an increment is applied before or after the
zero check, and how the first illegal event is reported without corrupting the
prior valid state.

### `timer-incubator-checkpoints`

Checkpoints are positive, unique elapsed offsets. A large advance can cross
many checkpoints; return them in deterministic ascending order and never emit
one twice after a later zero or negative-invalid update.

### `timer-evacuation-drill`

Use explicitly ordered stages with non-negative observed completion durations.
Clarify whether a result exactly at a deadline passes and whether a later
stage is evaluated after an earlier failure for diagnostic purposes.

### `timer-game-cooldown-registry`

Ability identifiers are unique and stable. An update advances every registered
ability simultaneously with saturation at zero; a reset of an unknown ability
or an already-ready ability has a documented no-op or error policy.

### `timer-oven-safety-lock`

Separate the lock's remaining duration from its bounded relock-credit count.
The root must specify whether relocking at exactly zero is allowed and ensure
that permanent disablement cannot be undone by a later advance or relock.

### `timer-build-lease`

Use monotonically ordered event sequence numbers supplied by the caller.
Renewal must check both worker identity and lease generation, and one advance
may expire several leases that are returned in stable identifier order.

### `timer-study-session-budget`

Represent activities and breaks as an ordered log. Define whether a mandatory
break is required before, after, or between focus thresholds, and reject an
event that would overspend the session without partially consuming its time.

## Materialization Requirements

Every candidate needs a task-specific C++17 public API. Do not make generic
`start`, `tick`, `remaining`, and `format` the primary assignment interface.
The starter must expose the domain records, policy inputs, outcome/diagnostic
type, and explicit invalid-input behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh locked sanitizer build; and
6. shared-denylist and semantic-contamination evidence.

Hidden tests must cover, where applicable:

- zero, one-unit, and very large elapsed advances, including checked arithmetic;
- exact-zero saturation, no negative remaining duration, and one-time expiry;
- equality at deadline, grace, cap, or extension thresholds;
- pause/resume/reset/relock/renewal transitions and no-state-mutation failures;
- empty and singleton collections, stable ordering, and simultaneous expiry;
- a large update crossing multiple stages, checkpoints, or expirations;
- randomized event traces checked against a small independent integer-duration
  oracle; and
- a final contamination screen proving that the root remains outside every
  benchmark family, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A task found to be a
close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.
