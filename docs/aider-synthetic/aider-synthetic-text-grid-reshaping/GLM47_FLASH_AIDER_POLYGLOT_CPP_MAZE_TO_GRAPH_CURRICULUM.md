# Maze-To-Graph Curriculum: Remediated Capability Family

Status: `local_family_verified` clean-room task-family material. This is not
SFT data, a dataset release, training authorization, or benchmark-uplift
evidence.

## Learning objective and holdout boundary

The family teaches materially different ways to transform text grids into
explicit graph representations: contraction, region incidence, low-link
decomposition, visibility, state expansion, condensation, product graphs,
weighted shortest paths, and domain-specific port or movement semantics. It
does not teach a generic maze solver and does not reuse official Aider
Polyglot wording, APIs, tests, references, or task assets. The 26 official C++
roots remain permanent holdouts.

The immutable legacy family used one renamed `GraphAudit`/four-neighbor BFS
template for every root. All 20 legacy objectives therefore have disposition
`replace`. The replacement roots are:

| Replacement ID | Primary graph mechanism |
| --- | --- |
| `tunnel-junction-contraction` | contract degree-two corridors into weighted junction edges |
| `gallery-door-region-graph` | label floor regions and connect them through typed doors |
| `aisle-segment-intersection-graph` | form a bipartite graph of maximal horizontal/vertical runs |
| `cave-bridge-block-tree` | discover bridges and contract bridge-deleted blocks |
| `subway-labelled-track-graph` | ray-trace orientation-compatible tracks between labelled stations |
| `garden-visibility-graph` | connect nearest orthogonally visible markers |
| `rack-port-capacity-graph` | trace labelled rack cables with bottleneck capacities |
| `ski-elevation-dag` | orient strict downhill arcs and memoize lodge reachability |
| `canal-lock-state-graph` | expand canal positions by open/closed lock state |
| `fire-time-expanded-egress` | combine fire-arrival times with safe time-expanded states |
| `ditch-flow-condensation` | compute SCCs and source components of a functional grid graph |
| `factory-conveyor-conflict-graph` | project directed moves into destination conflicts |
| `archive-turn-cost-graph` | lift aisles by arrival heading and assign turn costs |
| `trail-signpost-route-graph` | trace arrow automata between labelled signposts |
| `radar-range-visibility-graph` | cast bounded octilinear beacon rays |
| `hospital-block-cut-forest` | compute biconnected blocks and articulation incidence |
| `orchard-wrap-road-graph` | construct cylindrical seam adjacency |
| `sewer-glyph-port-graph` | validate reciprocal pipe ports before admitting edges |
| `concourse-gate-distance-graph` | compute one BFS distance field per labelled gate |
| `ice-slide-stop-graph` | simulate maximal slides between stable stopping cells |

## Materialization and completion

The authoritative contract and evidence table are in
`docs/aider-tasks-spec/aider-text-grid-reshaping/maze-to-graph.md`. The owner is
`src/w8_biayn/integrations/moonlight_maze_to_graph_aider_tasks.py`, with
one-to-one cases in `moonlight_maze_to_graph_cases.py`. Materialize only under
the re-verification tree:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_maze_to_graph_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

Each root exposes only docs plus its two declared editable files. References,
tests, negative fixtures, metadata, CMake, and receipts remain private. The
owner compares all 190 family pairs separately across the seven hard-rule
dimensions, plus all 190 aggregate pairs and 520 bound-holdout pairs. Coherent
domain/identifier-renamed, constants/policy-only, and opposite-end-selection
controls must fail all seven dimensions. The pinned network-disabled Docker
sanity run requires exactly three normal and three fresh ASan/UBSan CTest
discoveries per root, including a strict expected-failing negative target, and
also compiles and executes each coherent control in both modes. A passing
result is `local_family_verified`; dataset handoff remains `not_requested`.
