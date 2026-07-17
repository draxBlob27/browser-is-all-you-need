# Grid Ownership Mapping Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops diagram parsing, owner attribution, boundary rules,
and conflict diagnostics without recreating a classroom-garden or generic region task.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

All official Aider holdouts, including `kindergarten-garden`, are excluded.
Do not reuse their artifacts. Candidates must differ in diagram alphabet,
ownership model, output, invalid-input policy, and required diagnostic.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `ownership-marina-slips` | Marina slips | Attribute berth cells to vessels and report conflicts. |
| `ownership-farm-leases` | Farm leases | Map fields to leaseholders and count disputes. |
| `ownership-office-desks` | Office desks | Assign desks to teams and find unassigned workstations. |
| `ownership-rail-platforms` | Rail platforms | Attribute zones to services and detect overlaps. |
| `ownership-market-stalls` | Market stalls | Parse stalls into vendors and return frontage lengths. |
| `ownership-solar-array` | Solar array | Map panels to crews and flag mixed-owner strings. |
| `ownership-campsite-map` | Campsite map | Attribute plots to bookings and check path access. |
| `ownership-parking-permits` | Parking permits | Assign bays to permit groups and find illegal occupancy. |
| `ownership-warehouse-aisles` | Warehouse aisles | Map bins to zones and calculate usable capacity. |
| `ownership-orchard-blocks` | Orchard blocks | Attribute trees to growers and diagnose missing labels. |
| `ownership-harbor-quays` | Harbor quays | Assign quay sections and find disconnected concessions. |
| `ownership-lab-benches` | Lab benches | Map benches to experiments and reject incompatible contact. |
| `ownership-ski-runs` | Ski runs | Attribute piste cells to patrol sectors. |
| `ownership-city-gardens` | City gardens | Map cells to groups and calculate shared edges. |
| `ownership-museum-galleries` | Museum galleries | Attribute room tiles to exhibits and flag stray labels. |
| `ownership-flood-barriers` | Flood barriers | Assign segments to districts and report uncovered shore. |
| `ownership-data-center-racks` | Data-center racks | Map slots to customers and detect noncontiguous allocations. |
| `ownership-airport-gates` | Airport gates | Attribute gate cells to airlines with closure exceptions. |
| `ownership-river-rights` | River rights | Map channels to licensees and find ambiguous junctions. |
| `ownership-construction-lots` | Construction lots | Attribute parcels and compute exposed perimeter. |

## Materialization Requirements

Define legend, coordinate convention, and conflict policy. Hidden tests cover
empty diagrams, unknown symbols, disconnected regions, shared boundaries,
holes, edge cells, duplicate legends, stable diagnostics, and a per-cell oracle.

## Admission Boundary

All original-task provenance, C++17 reference, hidden Catch, normal/sanitizer,
contamination, family-split, rendering, and release requirements remain mandatory.
