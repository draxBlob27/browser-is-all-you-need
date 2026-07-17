# Date Difference Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum teaches Gregorian date-difference arithmetic: validated civil
dates, leap-aware month lengths, signed ordering, inclusive versus exclusive
endpoint policy, and checked day-count conversion. It does not add a fixed
future offset or solve weekday-in-month selection.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_CLOCK_AND_CALENDAR_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

Every official Aider Polyglot C++ root is a permanent holdout. In particular,
do not reuse `gigasecond`, `meetup`, or `clock` wording, API, types,
examples, tests, reference implementation, or model outputs. Do not construct
a near-copy by adding a constant date offset, a weekday-in-month lookup, or a
bare `days_between(a, b)` function with no domain behavior.

The proposals below are **not yet proven decontaminated**. They embed date
differences in independently authored records, policies, and diagnostic
results. Before admission, run the shared whole-slug benchmark denylist and
semantic-contamination checks; reject and backfill every near-match. Each
surviving root must differ from the holdout families in at least three
dimensions: public API/output, data collection/state model, endpoint/policy
rule, domain operation, and invalid-input behavior.

Inputs must be caller supplied and deterministic: no host clock, calendar or
time-zone API dependence, filesystem/network access, threads, or randomness.

## Online Material Status

Date-difference examples are useful only for private concept study or licensed
source discovery. They are not a drop-in SFT inventory. Each candidate must be
newly authored in C++17 with independent task text, starter API, reference,
examples, and tests, then pass provenance, license, oracle, sanitizer,
contamination, split, rendering, and release gates.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract | Deliberate separation from holdouts |
|---|---|---|---|
| `dated-warranty-audit` | Warranty audit | Classify product claims as in warranty, expired, or invalid using purchase, claim, and policy dates with an explicit inclusive end rule. | Produces claim diagnostics under a policy record, not a generic date offset. |
| `dated-project-burnup` | Project burn-up report | Calculate elapsed workdays between milestone records while excluding a caller-supplied holiday set and flag reversed milestones. | Uses a milestone collection plus an exclusion policy and report. |
| `dated-library-loan` | Library loan reconciliation | Compute overdue days and tiered fees from checkout, due, return, and closure dates; explain the first invalid date relation. | Combines multiple dates, fee tiers, and relationship diagnostics. |
| `dated-experiment-window` | Experiment observation window | Measure valid observation days within a study window after subtracting declared blackout spans. | Performs interval union/difference over date records with coverage output. |
| `dated-retention-review` | Records retention review | Determine remaining retention days and review status for archived records under category-specific retention policies. | Joins archive records to policy categories and emits typed action states. |

## Root-Specific Design Notes

These are authoring constraints, not hidden tests or reference answers. Names,
types, examples, and algorithms must be independently authored during
materialization.

### `dated-warranty-audit`

Specify whether a claim exactly on the policy end date is covered and whether
the purchase date itself counts as day zero or day one. An invalid calendar date
or claim before purchase must return a diagnostic without a partial result.

### `dated-project-burnup`

Holiday records have unique date identifiers and are excluded only when inside
the relevant interval. Define whether the end milestone is included and how a
duplicate holiday or a holiday on a weekend-like non-working day is reported.

### `dated-library-loan`

Use integer fee units and explicit tier boundaries. State whether a return on
the due date is late, how closures alter the count, and which invalid relation
wins if several are present.

### `dated-experiment-window`

Study and blackout spans use a documented half-open or closed endpoint
convention. Blackout spans may overlap or touch; canonicalize them before
subtraction and return remaining segments in deterministic order.

### `dated-retention-review`

Policies specify a positive retention duration and review lead time. Define
precedence among expired, review-due, and active states, including equality at
each threshold and an unknown policy category.

## Materialization Requirements

Every candidate needs a task-specific C++17 public API. Do not expose a bare
`days_between` or generic date-addition function as the assignment. The
starter must expose domain records, endpoint/policy inputs, structured results,
and explicit invalid-input behavior.

For every root, author:

1. a provenance record and original task specification;
2. a starter header/source pair with the domain-specific C++17 API;
3. an independent reference implementation;
4. visible examples and hidden Catch tests;
5. normal build plus a fresh locked sanitizer build; and
6. shared-denylist and semantic-contamination evidence.

Hidden tests must cover, where applicable:

- same-date, adjacent-date, ordered, and reversed endpoints;
- February 28/29, month/year boundaries, and Gregorian century rules;
- inclusive/exclusive endpoint and equality-at-policy-boundary behavior;
- empty/singleton record collections, duplicate IDs, and atomic failures;
- overlapping/touching blackout periods and category-policy lookup failures;
- randomized date records checked against a small independent proleptic
  Gregorian day-index oracle; and
- a final contamination screen proving the root remains outside every benchmark
  family, especially `clock`, `gigasecond`, and `meetup`.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates. A candidate found to be
a close semantic copy of an official benchmark must be rejected and backfilled;
it cannot be relabelled into this curriculum.

