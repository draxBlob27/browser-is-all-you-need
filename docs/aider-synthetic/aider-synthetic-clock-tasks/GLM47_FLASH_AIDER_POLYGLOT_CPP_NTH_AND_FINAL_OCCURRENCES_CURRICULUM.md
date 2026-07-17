# Nth And Final Occurrences Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum teaches selecting a numbered or final qualifying occurrence
from validated domain records: ordinal counting, final-element selection,
range bounds, filter predicates, absence handling, and deterministic ties. It
is deliberately not a generic calendar “nth weekday in a month” exercise.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

Every official Aider Polyglot C++ root is a permanent holdout. The `meetup`
task is especially relevant: do not reuse its wording, API, types,
constructor/enumeration shape, examples, tests, reference implementation, or
model outputs. Do not create a renamed function that returns the nth or last
weekday in a month. Also exclude `gigasecond` fixed-offset and `clock`
time-of-day contracts.

The proposals below are **not yet proven decontaminated**. They select
occurrences from independently authored domain collections with policy filters,
records, and diagnostics. Before admission, run the shared whole-slug benchmark
denylist and semantic-contamination checks; reject and backfill every near
match. Each surviving root must differ from `meetup` in at least three
dimensions: public API/output, source collection, qualification predicate,
range/policy model, selection result/diagnostic, and invalid-input behavior.

Inputs must be caller supplied and deterministic: no host clock, time-zone or
calendar API dependence, filesystem/network access, threads, or randomness.

## Online Material Status

Ordinal-occurrence examples are useful only for private concept study or
licensed source discovery. They are not a drop-in SFT inventory. Each candidate
must be newly authored in C++17 with independent task text, starter API,
reference, examples, and tests, then pass provenance, license, oracle,
sanitizer, contamination, split, rendering, and release gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from `meetup` |
|---|---|---|---|
| `occurrence-inspection-route` | Inspection route selector | Choose the nth or final passed inspection from ordered route records, subject to zone and severity filters. | Selects from supplied inspection records with multi-field predicates. |
| `occurrence-invoice-escalation` | Invoice escalation finder | Return the nth unresolved escalation or final overdue invoice within an account's ordered event history. | Uses account lifecycle records and status filtering, not weekdays. |
| `occurrence-lab-sample` | Lab sample checkpoint | Locate the nth valid measurement or final calibration-passing result in a sample run. | Filters typed experiment records with validity and threshold policy. |
| `occurrence-transit-stop` | Transit stop occurrence | Find the nth or final eligible stop in a route plan after accessibility and transfer constraints. | Uses an itinerary sequence and service constraints. |
| `occurrence-quality-audit` | Quality audit sampler | Select the nth defect matching a class or the final critical defect from batch inspection results. | Operates on production findings and severity rules. |
| `occurrence-support-breach` | Support breach reporter | Identify the nth SLA breach or final unresolved high-priority ticket in an ordered case ledger. | Uses ticket state, priority, and SLA diagnostics. |
| `occurrence-sports-qualifier` | Sports qualifier resolver | Select the nth qualifying attempt or final eligible athlete from event results under score and disqualification rules. | Applies competition records and tie/disqualification policy. |
| `occurrence-library-hold` | Library hold selector | Return the nth ready hold or final expired hold after patron-status and branch filters. | Works on a mutable queue snapshot with entitlement rules. |
| `occurrence-security-alert` | Security alert sampler | Find the nth alert requiring review or final unacknowledged critical alert in a bounded alert stream. | Uses alert category, acknowledgement, and retention policy. |
| `occurrence-maintenance-log` | Maintenance recurrence audit | Select the nth completed service or final overdue required service for each asset from its lifecycle log. | Groups per-asset records and returns compliance diagnostics. |

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Names,
types, examples, and algorithms must be independently authored during
materialization.

### `occurrence-inspection-route`

Route records have stable sequence IDs. Define whether an invalid record
terminates selection or is reported and skipped, and whether ordinal counting
happens before or after the zone/severity qualification predicate.

### `occurrence-invoice-escalation`

Events are ordered only after validating stable event sequence. Define how
resolved-after-escalation histories affect an unresolved filter and how an
account with fewer than N qualifying events is represented.

### `occurrence-lab-sample`

Measurements have validity state and a policy threshold. A failed calibration
must not qualify even if its numeric value passes; equal-position records need
a deterministic input-order rule.

### `occurrence-transit-stop`

Stops have stable route order and transfer/accessibility attributes. Define
whether the origin counts, whether a cancelled stop qualifies, and how a
missing requested ordinal produces an absent result.

### `occurrence-quality-audit`

Batch findings include a stable item ID and defect class. State whether a
re-inspected item may qualify twice and how final-critical selection handles a
later remediation record.

### `occurrence-support-breach`

Tickets have ordered status events, priority, and SLA evidence. A resolved
ticket must not remain final-unresolved; malformed event order must yield a
diagnostic rather than silently change ordinal counts.

### `occurrence-sports-qualifier`

Attempts include score, disqualification status, and stable attempt order.
Define score equality, athlete deduplication, and whether a disqualified later
attempt removes an earlier qualifying selection.

### `occurrence-library-hold`

Holds have stable IDs, branch, patron eligibility, and expiry state. The
selection is over an immutable snapshot; policy changes after the snapshot
must not affect the returned ordinal.

### `occurrence-security-alert`

The stream has a caller-supplied retention bound. Define whether suppressed or
acknowledged alerts count for ordinal purposes and return the final candidate
using a stable alert-ID tie rule.

### `occurrence-maintenance-log`

Group logs by asset ID after validating record order. A completed service may
satisfy only its declared requirement type; unsupported assets and missing
requirements must remain explicit diagnostics.

## Materialization Requirements

Every candidate needs a task-specific C++17 public API. Do not expose generic
`nth_weekday`, `last_weekday`, or a day-of-week/month enum as the assignment.
The starter must expose domain records, predicate/policy inputs, structured
results, and explicit invalid-input behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh locked sanitizer build; and
6. shared-denylist and semantic-contamination evidence.

Hidden tests must cover, where applicable:

- empty/singleton collections and requested ordinals one, final, and absent;
- qualification before counting, no qualifying records, and final selection;
- duplicate IDs, equal sequence positions, stable ties, and atomic failures;
- invalid records, changing lifecycle state, filters, and grouped asset/account
  behavior;
- long randomized record streams checked against a small independent filtered
  vector oracle; and
- a final contamination screen proving the root remains outside every benchmark
  family, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate found to be
a close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.

