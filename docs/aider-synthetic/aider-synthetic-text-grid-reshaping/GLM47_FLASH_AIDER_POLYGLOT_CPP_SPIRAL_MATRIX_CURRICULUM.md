# Spiral Matrix Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops boundary-driven grid traversal/fill with domain state,
rectangular dimensions, and validation; it does not recreate a generic spiral matrix.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

`spiral-matrix` is a permanent official Aider holdout. Never reuse its text,
API, examples, tests, reference, or a renamed fill/read contract. Every root
must differ in domain, surface, traversal policy, validation, and aggregate.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `spiral-museum-tour` | Museum tour | Visit room labels by rings and total ticket categories. |
| `spiral-orchard-harvest` | Orchard harvest | Collect fruit yields while skipping fenced plots. |
| `spiral-radar-sweep` | Radar sweep | Emit valid sweep cells and count contacts. |
| `spiral-archive-boxes` | Archive boxes | Assign accession IDs around storage layers. |
| `spiral-soil-sampler` | Soil sampler | Read depths in ring order and flag contamination. |
| `spiral-courtyard-lights` | Courtyard lights | Activate lamps around obstacles and report unlit cells. |
| `spiral-cargo-inspection` | Cargo inspection | Traverse bays from a corner and find the first defect. |
| `spiral-paint-mixer` | Paint mixer | Place batches in rings and calculate color conflicts. |
| `spiral-library-shelving` | Library shelving | Assign books through layers with blocked niches. |
| `spiral-irrigation-valves` | Irrigation valves | Activate valves by ring and total demand. |
| `spiral-drone-photography` | Drone photography | Generate capture routes with battery checkpoints. |
| `spiral-sand-tray` | Sand tray | Read symbol layers and return layer histograms. |
| `spiral-circuit-probe` | Circuit probe | Visit pads by boundary order and stop on an open circuit. |
| `spiral-evacuation-search` | Evacuation search | Inspect room rings excluding sealed rooms. |
| `spiral-greenhouse-seeding` | Greenhouse seeding | Place seed lots and retain lot-to-cell mapping. |
| `spiral-satellite-panels` | Satellite panels | Enumerate panel inspections by ring. |
| `spiral-ice-core-display` | Ice-core display | Fill exhibit samples with depth labels. |
| `spiral-board-game-setup` | Board-game setup | Place terrain tokens with forbidden cells. |
| `spiral-water-quality` | Water-quality grid | Traverse cells and aggregate by completed ring. |
| `spiral-warehouse-robot` | Warehouse robot | Produce obstacle-aware ring routes and unreachable slots. |

## Materialization Requirements

Require typed coordinates and a domain result, not `spiral(rows, columns)`.
Hidden tests cover one row/column, odd/even rectangles, blocked cells,
start/direction policy, duplicate prevention, exact visit counts, and a
coordinate-set oracle.

## Admission Boundary

Every candidate remains subject to provenance, C++17 oracle, sanitizer,
holdout/semantic screening, family isolation, rendering, token, and release gates.
