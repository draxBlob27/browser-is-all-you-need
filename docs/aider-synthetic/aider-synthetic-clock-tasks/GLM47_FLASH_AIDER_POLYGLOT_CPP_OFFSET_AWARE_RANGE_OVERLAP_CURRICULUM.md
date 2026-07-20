# Offset-Aware Range Overlap Curriculum: Decontaminated Capability

Status: remediated local-family curriculum. The historical ten-root template
is immutable audit input. The corrected v3 owner emits ten roots beneath the requested
parallel `aider-text-grid-reshaping` re-verification tree, within the
user-authorized hard-rule bound of 8–12. This is not SFT data or an online
dataset.

This curriculum teaches comparison of local ranges after conversion through
caller-supplied fixed UTC offsets: interval normalization, date rollover,
half-open/closed endpoints, overlap, intersection, and deterministic
allocation. It does not model daylight-saving transitions or expose a
general-purpose clock/time-zone conversion API.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

Every official Aider Polyglot C++ root is a permanent holdout. In particular,
do not reuse `clock`, `gigasecond`, or `meetup` wording, API, types,
examples, tests, references, or model outputs. Do not create a renamed clock
exercise that only adds an offset and formats a local time, or a bare
`ranges_overlap(a, b)` function without domain policy.

The proposals below are **not yet proven decontaminated**. They use
independently authored domain records, fixed-offset policies, allocation or
diagnostic results, and range collections. Before admission, run the shared
whole-slug benchmark denylist and semantic-contamination checks; reject and
backfill every near match. Each surviving root must differ from the holdout
families in at least three dimensions: public API/output, range/collection
model, offset policy, resource/eligibility rule, and invalid-input behavior.

Offsets are signed whole minutes supplied by the caller under a documented
bound. Do not read a host clock, query a time-zone/DST database, access the
filesystem/network, create threads, or rely on randomness.

## Online Material Status

Offset-overlap and meeting-time examples are useful only for private concept
study or licensed source discovery. They are not a drop-in SFT inventory. Each
candidate must be newly authored in C++17 with independent task text, starter
API, reference, examples, and tests, then pass provenance, license, oracle,
sanitizer, contamination, split, rendering, and release gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from holdouts |
|---|---|---|---|
| `offset-flight-crew-rest` | Flight crew rest verifier | Determine whether crew rest intervals recorded at different fixed-offset bases satisfy a minimum common-instant rest rule. | Uses crew records, legal rest policy, and compliance diagnostics. |
| `offset-remote-support` | Remote support handoff | Find overlap between regional support shifts, allocate a required handoff duration, and report the earliest viable pair. | Selects from shift collections with staffing and tie-break policy. |
| `offset-distributed-deploy` | Distributed deployment window | Validate whether service maintenance windows from regions with fixed offsets share a sufficient deployment intersection. | Works on multi-service windows and capacity requirements. |
| `offset-crossborder-delivery` | Cross-border delivery slot | Match a warehouse dispatch range to a recipient acceptance range after each location's fixed offset and return legal slot options. | Combines entitlement windows and sorted alternative results. |
| `offset-telehealth-roster` | Telehealth roster planner | Assign a clinician to appointments by instant overlap while enforcing local-clinic availability and daily allocation caps. | Uses assignment state, caps, and two local representations. |
| `offset-satellite-contact` | Satellite contact scheduler | Intersect ground-station visibility ranges expressed in fixed local offsets and reserve non-overlapping contact passes. | Adds resource reservation and pass-conflict behavior. |
| `offset-build-freeze` | Build freeze evaluator | Classify planned releases against regional freeze ranges and return the first blocking jurisdiction. | Applies ordered policy ranges and blocking diagnostics. |
| `offset-research-coverage` | Research coverage audit | Measure common observation coverage across instrument windows at fixed offsets, excluding declared calibration spans. | Uses interval intersection/subtraction and coverage aggregation. |
| `offset-emergency-escalation` | Emergency escalation relay | Choose a relay team whose duty range overlaps an incident response window after fixed-offset normalization. | Searches a team roster under skill and overlap constraints. |
| `offset-market-auction` | Market auction overlap | Admit bids only when trading sessions overlap in a common instant range and choose the session with the longest valid intersection. | Combines session policy, bid records, and deterministic selection. |

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Names,
types, examples, and algorithms must be independently authored during
materialization.

### `offset-flight-crew-rest`

Rest records include stable crew and base IDs, local range, and fixed offset.
Define a half-open endpoint convention, required rest equality behavior, and
how an invalid offset or reversed local range is diagnosed.

### `offset-remote-support`

Shift ranges are normalized to a bounded instant horizon. Define whether
touching shifts provide zero or valid handoff overlap, how equally early pairs
are ordered, and whether one agent can be assigned twice.

### `offset-distributed-deploy`

Service windows have stable service IDs and minimum required intersection.
A missing service or unsupported offset must produce an explicit failure rather
than being omitted from the common-window calculation.

### `offset-crossborder-delivery`

Dispatch and acceptance ranges are policy records with a shared delivery
duration. Define whether a route crossing local midnight is valid and return
legal alternatives in deterministic instant order.

### `offset-telehealth-roster`

Appointments carry clinic-local records and a fixed clinic offset. Daily cap
counting must use the stated local-day policy after an assignment; rejected
assignments cannot consume clinician capacity.

### `offset-satellite-contact`

Passes have stable IDs and resource duration. Define contact endpoint behavior,
whether touching contacts conflict, and how an unavailable ground station is
reported without changing existing reservations.

### `offset-build-freeze`

Freeze ranges have precedence and jurisdiction IDs. A release that touches a
freeze boundary requires explicit classification, and the first blocker must be
chosen under a documented jurisdiction/order tie rule.

### `offset-research-coverage`

Calibration spans may overlap or touch and must be canonicalized after offset
normalization. Define whether coverage exactly at the required threshold passes
and how empty instrument data is represented.

### `offset-emergency-escalation`

Teams have skills, capacity, and stable IDs. Define whether a team exactly
available at an incident endpoint qualifies and return no-team diagnostics when
every otherwise suitable team fails overlap.

### `offset-market-auction`

Sessions and bids use caller-supplied offsets only. Define session endpoint
policy, equal longest-intersection ties, and handling of a bid whose local
session range is malformed or exceeds the supported instant horizon.

## Materialization Requirements

Every candidate needs a task-specific C++17 public API. Do not expose generic
`convert_offset`, `local_time`, or `ranges_overlap` methods as the
assignment. The starter must expose domain records, offset bounds, endpoint
policy, structured results, and explicit invalid-input behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh locked sanitizer build; and
6. shared-denylist and semantic-contamination evidence.

Hidden tests must cover, where applicable:

- positive, negative, zero, and extreme allowed fixed offsets;
- local ranges crossing midnight and common-instant ranges crossing a date
  boundary;
- empty/singleton collections, invalid/reversed ranges, and unsupported offsets;
- touching, overlapping, nested, and disjoint ranges under declared endpoint
  policy;
- equality at rest, handoff, capacity, coverage, and freeze boundaries;
- stable ties, duplicate IDs, rejected insertion, and no-state-mutation failure;
- randomized fixed-offset interval traces checked against a small independent
  unwrapped-instant oracle; and
- a final contamination screen proving the root remains outside every benchmark
  family, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate found to be
a close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.

## V3 Remediation Inventory

The proposal IDs above describe the immutable legacy input. The counted v3
inventory is `offset-build-freeze`, `offset-border-slot-enumerator`,
`offset-deployment-quorum-sweep`, `offset-relay-capacity-matching`,
`offset-rest-gap-compliance`, `offset-auction-liquidity-intersection`,
`offset-support-coverage-chain`,
`offset-observation-coverage-subtraction`,
`offset-station-contact-weighted-schedule`, and
`offset-clinic-capacity-assignment`. Their mechanisms, dispositions, public
contracts, negatives, 45-pair seven-dimension rule, coherent controls, and
Docker acceptance are normative in
`docs/aider-tasks-spec/aider-text-grid-reshaping/offset-aware-range-overlap.md`.
The v2 identifier-preserving 0.98-overlap screen and its receipt are preserved
as invalidated evidence: they admitted two augmenting-path matching roots. V3
replaces the support root with a minimum interval-cover frontier sweep and
normalizes every user-defined/domain identifier, literal, and endpoint
direction before making each of the 45 by 7 conjunctive decisions.
