# Transpose Curriculum: Decontaminated Capability

Status: curriculum-design note. These original task concepts are not admitted
SFT roots or an online dataset.

This curriculum develops rectangular row/column reshaping, dimension checks,
ragged-input policies, and coordinate-preserving transformations. It does not
propose a renamed generic transpose exercise.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md`,
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`, and
`docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

All 26 official Aider Polyglot C++ roots and semantic copies are permanent
holdouts. Do not reuse their wording, APIs, examples, tests, references, or
model outputs. Each candidate must use a domain-specific C++17 API and differ
in input model, output shape, validation policy, and required query. Run the
whole-slug denylist and semantic contamination checks; reject and backfill
near-matches.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `transpose-lab-readings` | Lab readings ledger | Convert day-major measurements into sensor histories and flag gaps. |
| `transpose-class-register` | Class register | Turn lesson rows into student summaries with absences. |
| `transpose-market-quotes` | Market quote board | Reorient vendor prices and return each item's cheapest vendor. |
| `transpose-survey-answers` | Survey answers | Convert respondent answers into question cohorts with invalid counts. |
| `transpose-freight-manifest` | Freight manifest | Reorient truck sheets into package locations with duplicate detection. |
| `transpose-weather-log` | Weather log | Convert station-day cells into daily regional observations. |
| `transpose-choir-rehearsal` | Choir rehearsal | Turn rehearsal rows into singer histories and attendance streaks. |
| `transpose-exam-markbook` | Exam markbook | Reorient marks and calculate per-assignment score bands. |
| `transpose-library-loans` | Library loans | Convert branch-day totals into branch timelines with missing days. |
| `transpose-factory-shifts` | Factory shifts | Turn shift rows into machine records and report stalled machines. |
| `transpose-garden-plots` | Garden plots | Reorient plot observations into weekly crop summaries. |
| `transpose-seat-audit` | Seat audit | Turn flight snapshots into seat histories with cabin labels. |
| `transpose-diet-diary` | Diet diary | Convert meal rows into nutrient timelines with unit validation. |
| `transpose-call-center` | Call-center board | Reorient agent-hour counts and find the busiest valid hour. |
| `transpose-museum-visits` | Museum visits | Turn room-day counts into day itineraries and validate rooms. |
| `transpose-network-probes` | Network probes | Convert probe outcomes into target reliability records. |
| `transpose-training-load` | Training load | Reorient athlete metrics and report incomplete programs. |
| `transpose-river-samples` | River samples | Convert site-month samples into monthly comparisons with sentinels. |
| `transpose-inventory-cycle` | Inventory cycle | Turn warehouse counts into item histories and reconcile mismatches. |
| `transpose-energy-meters` | Energy meters | Reorient meter intervals into totals with checked arithmetic. |

## Materialization Requirements

Every root needs a typed task-specific C++17 API; never expose only
`transpose(vector<vector<T>>)`. Hidden tests must cover empty/singleton input,
one-row/one-column rectangles, unequal rows under the stated policy, identity
ordering, and a coordinate-oracle or round-trip property.

## Admission Boundary

This document does not bypass provenance, oracle, sanitizer, contamination,
family-split, rendering, token/mask, or release verification gates.
