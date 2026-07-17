# Maze To Graph Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops parsing walkable grids into vertices/edges, coordinate
labels, adjacency policy, entrances, and disconnected-component diagnostics.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

All official holdouts are excluded. Do not create a generic maze solver; every
candidate needs a domain grid alphabet, graph API, edge policy, and result
beyond pathfinding. Semantic screening rejects close benchmark families.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `graph-mine-tunnels` | Mine tunnels | Parse tunnels into adjacency and list isolated chambers. |
| `graph-museum-rooms` | Museum rooms | Build room-door graph and count emergency exits per component. |
| `graph-warehouse-aisles` | Warehouse aisles | Convert aisles to graph nodes and identify dead ends. |
| `graph-cave-survey` | Cave survey | Parse passages and report junction degree histograms. |
| `graph-subway-map` | Subway map | Convert track diagram cells into station adjacency. |
| `graph-garden-paths` | Garden paths | Parse paths and find inaccessible planting zones. |
| `graph-data-center` | Data center | Convert cable corridors into rack connectivity. |
| `graph-ski-resort` | Ski resort | Parse runs/lifts and report reachable lodges. |
| `graph-harbor-canals` | Harbor canals | Build canal graph and detect closed basins. |
| `graph-fire-escape` | Fire escape | Parse corridors and list rooms without exit access. |
| `graph-irrigation-ditches` | Irrigation ditches | Convert ditch map to adjacency and report sources. |
| `graph-robot-factory` | Robot factory | Parse lanes and identify one-way junction conflicts. |
| `graph-archive-stacks` | Archive stacks | Convert stack aisles into graph components. |
| `graph-camp-trails` | Camp trails | Parse trail cells and count signed intersections. |
| `graph-radar-corridors` | Radar corridors | Convert clear sectors into adjacency with blocked cells. |
| `graph-hospital-halls` | Hospital halls | Build ward hallway graph and find articulation candidates. |
| `graph-orchard-roads` | Orchard roads | Parse service roads and report connected blocks. |
| `graph-sewer-lines` | Sewer lines | Convert pipe diagram into junction degrees. |
| `graph-airport-concourse` | Airport concourse | Parse walkways and map gate accessibility. |
| `graph-ice-caves` | Ice caves | Build cave graph and identify bridge passages. |

## Materialization Requirements

Define walkable alphabet, coordinate origin, four/eight-neighbor and directed
edge policy, and output order. Hidden tests cover empty maps, singleton nodes,
walls, borders, multiple entrances, cycles, disconnected components, and an
independent coordinate-neighbor graph oracle.

## Admission Boundary

All provenance, original C++17 API/reference/tests, sanitizer, contamination,
family isolation, rendering, token, and release requirements remain mandatory.
