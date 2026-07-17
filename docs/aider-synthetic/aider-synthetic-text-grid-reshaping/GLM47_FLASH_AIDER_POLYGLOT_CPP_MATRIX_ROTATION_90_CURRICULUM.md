# Matrix Rotation By 90 Degrees Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops coordinate mapping, quarter-turn orientation, in-place
layer movement, and metadata preservation for square grids.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

All official Aider holdouts and close semantic copies are excluded. Every root
must use domain cells and a domain query, with distinct API, orientation,
mutation contract, and edge cases; semantic review remains blocking.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `rotate-aerial-tiles` | Aerial tiles | Rotate a survey tile and update north-edge summaries. |
| `rotate-circuit-board` | Circuit board | Rotate placements while checking connectors. |
| `rotate-chess-analysis` | Chess analysis | Rotate a position diagram and map side metadata. |
| `rotate-museum-floorplan` | Museum floorplan | Turn rooms and return doors on the entrance edge. |
| `rotate-satellite-camera` | Satellite camera | Rotate classifications and count corner coverage. |
| `rotate-warehouse-pallets` | Warehouse pallets | Reorient pallets preserving hazards and access lanes. |
| `rotate-radar-sector` | Radar sector | Rotate contacts and recompute quadrant tallies. |
| `rotate-quilt-block` | Quilt block | Rotate patches and validate directional seams. |
| `rotate-garden-bed` | Garden bed | Turn plant positions and report path-facing crops. |
| `rotate-escape-map` | Escape map | Rotate symbols and remap exit directions. |
| `rotate-puzzle-tile` | Puzzle tile | Rotate a tile and return connector signature. |
| `rotate-solar-panel` | Solar panel | Reorient states and count shaded edges. |
| `rotate-lab-sample-rack` | Sample rack | Rotate slots and preserve barcode mapping. |
| `rotate-storm-grid` | Storm grid | Rotate warnings and compare boundary exposure. |
| `rotate-theater-lights` | Theater lights | Rotate fixtures and directional beam flags. |
| `rotate-orchard-spray` | Orchard spray | Reorient treatment cells and count path adjacency. |
| `rotate-tactical-map` | Tactical map | Rotate units and transform headings. |
| `rotate-factory-inspection` | Factory inspection | Turn defects and report loading-edge defects. |
| `rotate-ice-rink-drills` | Ice rink drills | Rotate markers retaining team-color counts. |
| `rotate-archive-shelves` | Archive shelves | Reorient labels and return accession order. |

## Materialization Requirements

Specify direction, origin, mutation semantics, and size limits. Hidden tests
cover sizes 0/1/2, all turns, corner/edge/interior cells, four-turn identity,
metadata transforms, ragged input, and a coordinate-map oracle.

## Admission Boundary

Candidates require original C++17 APIs and all provenance, oracle, sanitizer,
contamination, family-split, renderer, token/mask, and release gates.
