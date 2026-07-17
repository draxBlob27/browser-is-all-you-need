# Table Pivot Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops header realignment, row/column reshaping, missing-cell
policy, stable ordering, and typed aggregation for tabular records.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

All official holdouts are excluded. Do not make a bare CSV transpose task;
each root needs a domain schema, identity keys, missing/duplicate policy, and
a query or diagnostic that separates it from generic table reshaping.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `pivot-clinic-visits` | Clinic visits | Pivot patient observations into date columns with missing flags. |
| `pivot-market-sales` | Market sales | Pivot vendor receipts into product totals and duplicate diagnostics. |
| `pivot-school-grades` | School grades | Turn grade records into subject columns with absent assessments. |
| `pivot-river-quality` | River quality | Pivot site samples into month columns and validate units. |
| `pivot-warehouse-orders` | Warehouse orders | Turn order lines into item-day demand tables. |
| `pivot-flight-delays` | Flight delays | Pivot delay records by airport and hour. |
| `pivot-energy-bills` | Energy bills | Turn meter records into account-period billing rows. |
| `pivot-farm-harvests` | Farm harvests | Pivot crop lots into field-season totals. |
| `pivot-museum-tickets` | Museum tickets | Turn visit records into exhibit-day attendance columns. |
| `pivot-lab-results` | Lab results | Pivot assays into sample analyte columns. |
| `pivot-call-center` | Call center | Turn calls into agent-shift performance rows. |
| `pivot-transit-ridership` | Transit ridership | Pivot stop counts into route-date tables. |
| `pivot-library-circulation` | Library circulation | Turn loans into branch-category summary tables. |
| `pivot-solar-output` | Solar output | Pivot inverter readings into panel-hour output. |
| `pivot-hotel-bookings` | Hotel bookings | Turn stays into room-date occupancy columns. |
| `pivot-orchard-inspections` | Orchard inspections | Pivot tree checks into block-metric tables. |
| `pivot-factory-defects` | Factory defects | Turn defect events into line-shift counts. |
| `pivot-emergency-supplies` | Emergency supplies | Pivot stock checks into depot-item tables. |
| `pivot-research-cohorts` | Research cohorts | Turn measurements into participant-visit columns. |
| `pivot-community-events` | Community events | Pivot registrations into venue-session counts. |

## Materialization Requirements

Specify schema, header order, identity keys, missing-cell representation,
duplicate merge/reject behavior, and numeric aggregation. Hidden tests cover
empty input, one key, missing combinations, duplicate records, stable order,
ragged source rows, invalid headers, and pivot/unpivot or map-based oracles.

## Admission Boundary

Original C++17 APIs, provenance, reference and hidden Catch tests, normal and
sanitizer proof, contamination/family review, and every release gate are required.
