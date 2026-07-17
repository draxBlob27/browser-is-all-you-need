# Flood Fill Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops connected-region selection, neighborhood policy,
mutation control, region statistics, and boundary-aware relabeling.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

All official holdouts are excluded. Candidates must not be a bare paint-bucket
function: they require a domain input/output, explicit connectivity, boundary
rules, and meaningful diagnostic or aggregate.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `fill-wildfire-sector` | Wildfire sector | Relabel a burn region and compute its perimeter. |
| `fill-lake-survey` | Lake survey | Mark connected water cells and measure shoreline contact. |
| `fill-warehouse-spill` | Warehouse spill | Identify a spill region avoiding sealed storage cells. |
| `fill-museum-restoration` | Museum restoration | Recolor one mural region and preserve protected pigments. |
| `fill-crop-disease` | Crop disease | Mark connected infected plots and report row spread. |
| `fill-mine-tunnels` | Mine tunnels | Label reachable tunnel areas with four-neighbor movement. |
| `fill-ice-thickness` | Ice thickness | Group equal-class ice cells and find the largest safe patch. |
| `fill-radar-clouds` | Radar clouds | Relabel cloud cells using eight-neighbor connectivity. |
| `fill-city-blocks` | City blocks | Mark contiguous construction zones excluding roads. |
| `fill-coral-reef` | Coral reef | Classify connected bleaching patches and count edges. |
| `fill-circuit-traces` | Circuit traces | Label conductive paths while stopping at insulated cells. |
| `fill-orchard-frost` | Orchard frost | Mark connected frost pockets and list affected trees. |
| `fill-river-pollution` | River pollution | Relabel plume cells and detect border escape. |
| `fill-ski-avalanche` | Ski avalanche | Mark slide regions and report lift-line intersections. |
| `fill-quarry-material` | Quarry material | Identify contiguous ore veins under a threshold rule. |
| `fill-garden-mulch` | Garden mulch | Spread mulch within a bed while avoiding stones. |
| `fill-archive-damage` | Archive damage | Label connected damaged pages in a scan grid. |
| `fill-theater-smoke` | Theater smoke | Mark smoke regions and calculate exit-adjacent cells. |
| `fill-harbor-oil` | Harbor oil | Trace an oil patch with barrier cells. |
| `fill-solar-soiling` | Solar soiling | Relabel dirty-panel clusters and summarize by row. |

## Materialization Requirements

Specify four/eight-neighbor connectivity, source/target behavior, mutation
semantics, and border policy. Hidden tests cover no-op replacement, singleton,
disconnected equal cells, diagonals, blocked borders, large iterative cases,
and an independent BFS/DFS region oracle.

## Admission Boundary

Candidates need original C++17 APIs, provenance, reference/hidden tests,
normal/sanitizer proof, contamination/family checks, and all release gates.
