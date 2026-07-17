# Sparse Matrix Encoding Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops dense/coordinate-list conversion, default-value
policy, canonical ordering, duplicate handling, and round-trip validation.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

All official holdouts are excluded. Do not supply a bare generic sparse codec;
each candidate needs a domain model, metadata policy, validation result, and
query distinct from any benchmark or source family.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `sparse-power-outages` | Power outages | Encode outage cells and query affected feeders. |
| `sparse-farm-irrigation` | Farm irrigation | Store watered plots and calculate dry regions. |
| `sparse-library-shelves` | Library shelves | Encode occupied slots and find free shelf runs. |
| `sparse-transit-delays` | Transit delays | Store delayed stops and aggregate route disruption. |
| `sparse-radar-contacts` | Radar contacts | Encode contact cells with confidence values. |
| `sparse-paint-defects` | Paint defects | Convert defect maps and count defects by panel. |
| `sparse-hospital-beds` | Hospital beds | Encode occupied beds and validate ward dimensions. |
| `sparse-solar-shade` | Solar shade | Store shaded panels and compute exposure totals. |
| `sparse-orchard-pests` | Orchard pests | Encode infected trees and list affected rows. |
| `sparse-parking-sensors` | Parking sensors | Store occupied bays and query nearest free bay. |
| `sparse-warehouse-stock` | Warehouse stock | Encode nonempty bins and reconcile duplicate scans. |
| `sparse-flood-markers` | Flood markers | Store inundated cells and calculate shore contact. |
| `sparse-constellation` | Constellation | Encode stars and report bounding boxes. |
| `sparse-game-terrain` | Game terrain | Store nondefault tiles and validate coordinates. |
| `sparse-crop-yields` | Crop yields | Encode nonzero yields and aggregate by field. |
| `sparse-network-failures` | Network failures | Store failed links in a grid and query severity. |
| `sparse-seat-reservations` | Seat reservations | Encode reserved seats and group by cabin. |
| `sparse-lab-assays` | Lab assays | Store positive wells and detect duplicate entries. |
| `sparse-fire-hotspots` | Fire hotspots | Encode heat cells and calculate maximum row load. |
| `sparse-museum-sensors` | Museum sensors | Store triggered cells and reconstruct floor state. |

## Materialization Requirements

Define dimensions, default value, coordinate order, duplicate policy, and
out-of-range errors. Hidden tests cover empty/all-default grids, duplicates,
boundary coordinates, decode(encode) equality, canonical order, and an
independent dense-grid oracle.

## Admission Boundary

All original-task provenance, C++17 reference/tests, sanitizer, contamination,
family isolation, renderer/token, and release gates remain mandatory.
