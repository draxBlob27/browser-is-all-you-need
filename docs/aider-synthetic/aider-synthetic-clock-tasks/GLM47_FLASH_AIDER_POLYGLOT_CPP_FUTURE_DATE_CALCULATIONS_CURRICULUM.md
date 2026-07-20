# Future-Date Calculations Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

Remediation status (2026-07-18): the legacy ten-root template family was
audited with `remediate-family-reverify.md`. Under the user-authorized 8–12
hard count, eight independently implemented replacements are generated at
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/future-date-calculations/`;
`future-publication-embargo` and `future-lease-notices` are rejected rather
than retained as policy-only padding. The normative audit and exact
dispositions are in
`docs/aider-tasks-spec/aider-text-grid-reshaping/future-date-calculations.md`.
The immutable legacy family remains under `aider-dates-and-clocks` because the
user-supplied `FAMILY_TYPE` controls the parallel v2 location, not v1 history.

This curriculum develops checked Gregorian forward-date calculations under
domain policy: variable day/month offsets, leap-aware transitions, bounded
horizons, end-of-month clamp rules, exclusions, and multi-record diagnostics.
It does not ask for a fixed number of seconds after one timestamp.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

Every official Aider Polyglot C++ root is a permanent holdout. In particular,
`gigasecond` is excluded: do not reuse its wording, API, types, examples,
tests, reference implementation, or model outputs. Do not create a renamed
task whose behavior is simply adding a single fixed seconds offset to a start
date/time. Also exclude `meetup` weekday-in-month and `clock` time-of-day
contracts.

The proposals below are **not yet proven decontaminated**. They require
independently authored domain policies, multiple inputs or records, and typed
diagnostic results. Before admission, run the shared whole-slug benchmark
denylist and semantic-contamination checks; reject and backfill every near
match. Each surviving root must differ from `gigasecond` in at least three
dimensions: public API/output, offset source or policy, collection/state model,
calendar/exclusion rule, result/diagnostic behavior, and invalid-input policy.

Inputs must be caller supplied and deterministic: no host clock, time-zone or
calendar API dependence, filesystem/network access, threads, or randomness.

## Online Material Status

Future-date examples are useful only for private concept study or licensed
source discovery. They are not a drop-in SFT inventory. Each candidate must be
newly authored in C++17 with independent task text, starter API, reference,
examples, and tests, then pass provenance, license, oracle, sanitizer,
contamination, split, rendering, and release gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from `gigasecond` |
|---|---|---|---|
| `future-warranty-milestones` | Warranty milestone planner | Calculate inspection, standard-expiry, and extended-expiry dates from product policy months and optional registration events. | Returns several policy-derived milestones and registration diagnostics. |
| `future-crop-treatment` | Crop treatment forecast | Generate treatment dates from a planting record, growth-stage offsets, weather blackout dates, and a maximum season horizon. | Uses a schedule collection with exclusions and unscheduled outcomes. |
| `future-invoice-followups` | Invoice follow-up workflow | Produce reminder and escalation dates from invoice status, payment terms, grace rules, and prior-contact history. | Applies lifecycle state and suppresses redundant future actions. |
| `future-licence-renewal` | Licence renewal timeline | Compute notification, renewal, grace, and reinstatement milestones from a licence category policy. | Uses category-specific multi-stage policy rather than one fixed offset. |
| `future-lab-sample` | Lab sample viability forecast | Determine assay, warning, and discard dates from sample type, storage class, and validated handling interruptions. | Joins sample records to stability rules and interruption diagnostics. |
| `future-construction-deadline` | Construction deadline recovery | Recalculate phased deadlines after approved delay amendments and non-working closure spans. | Processes an amendment log and closure collection with ordering checks. |
| `future-vaccine-series` | Vaccine series scheduler | Offer the earliest eligible next-dose dates from dose history, minimum/maximum interval rules, and catch-up policy. | Uses patient dose history plus range constraints, not a single addition. |
| `future-equipment-calibration` | Equipment calibration forecast | Schedule next calibration by usage cadence or calendar limit, choose the earlier trigger, and report why. | Compares independent trigger sources with an explanatory result. |
| `future-publication-embargo` | Publication embargo manager | Compute release eligibility after embargo duration, revision extensions, and legal-hold states. | Mutates a publication lifecycle with hold precedence and extensions. |
| `future-lease-notices` | Lease notice generator | Generate renewal and vacate notice deadlines from lease terms, notice periods, and tenant election records. | Combines contractual policies and election-state outcomes. |

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Names,
types, examples, and algorithms must be independently authored during
materialization.

### `future-warranty-milestones`

Define end-of-month behavior for policy-month additions and precedence when
registration occurs after an otherwise expired standard warranty. Unsupported
product policies must return an explicit diagnostic.

### `future-crop-treatment`

Growth-stage offsets are positive, policy-owned values. Blackouts have stable
IDs; specify whether a blocked treatment moves forward, is skipped, or is
reported as unscheduled when the season horizon would be exceeded.

### `future-invoice-followups`

Contact history uses stable action IDs. A paid or disputed invoice must suppress
future collection actions under an explicit precedence rule, and a duplicate
contact must not create duplicate reminders.

### `future-licence-renewal`

Policies define notification lead, renewal boundary, grace, and reinstatement
durations. Equality at every boundary must produce a stated status, including a
licence category unknown to the policy table.

### `future-lab-sample`

Storage class and handling interruption records are caller supplied. Define
whether interruptions shorten viability additively or use the worst observed
penalty, and reject an interruption outside the sample lifecycle.

### `future-construction-deadline`

Amendments have stable sequence IDs and effective ordering. Closure spans must
use an explicit endpoint policy; a rejected amendment cannot partially update
any later phase deadline.

### `future-vaccine-series`

Dose records are sorted only after validation. Define minimum/maximum interval
equality behavior, contraindication/catch-up precedence, and whether several
eligible dates are alternatives or sequential milestones.

### `future-equipment-calibration`

Calendar and usage triggers are independently validated. Define a deterministic
tie rule when triggers agree and an error result when usage data is stale or
the calendar date exceeds the supported range.

### `future-publication-embargo`

Revision extensions and legal holds have stable IDs. A legal hold must override
ordinary eligibility; duplicate or conflicting extensions must produce
diagnostics without changing the last valid release date.

### `future-lease-notices`

Terms, notice periods, and elections are policy records. Specify whether a
tenant election after the relevant notice deadline is invalid or causes an
alternate outcome, and define end-of-month clamp behavior for leases.

## Materialization Requirements

The counted v2 inventory is exactly eight roots. Every unordered pair must
differ materially and separately in public API, owned state/algorithm,
mutation or selection rules, invalid and boundary behavior, reference control
flow, deterministic oracle, and topic-specific negative fixture. The family
owner must reject domain/identifier-renamed, constants/policy-only, and
opposite-end-selection controls after proving each is coherent, buildable, and
rejected by executed tests. Any change to this contract, owner, emitted
artifacts, focused tests, or evidence invalidates the prior receipt and requires
complete regeneration and Docker re-verification.

Every candidate needs a task-specific C++17 public API. Do not expose generic
`add_seconds`, `add_days`, `Date::plus`, or a fixed-offset function as the
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

- leap-year February, month-end clamping, century, and year-end transitions;
- zero/positive policy offsets, checked range limits, and invalid civil dates;
- equality at notification, grace, expiry, minimum/maximum, and horizon limits;
- empty/singleton histories, duplicate IDs, stable ties, and atomic failures;
- blackout/closure/hold precedence, amendments, and rejected policy records;
- randomized policy/record inputs checked against a small independent
  proleptic-Gregorian calendar oracle; and
- a final contamination screen proving the root remains outside every benchmark
  family, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate found to be
a close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.
