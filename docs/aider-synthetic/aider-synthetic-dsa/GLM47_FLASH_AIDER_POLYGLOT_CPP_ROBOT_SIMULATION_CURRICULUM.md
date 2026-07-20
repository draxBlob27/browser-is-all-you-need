# Robot State-Simulation Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum targets stateful simulation: typed commands, orientation or
mode transitions, constrained movement, resource state, invalid-action policy,
and observable execution traces. It does **not** propose renamed copies of a
canonical turn-left/turn-right/advance robot exercise.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

The official Aider C++ benchmark holdout set remains excluded in its entirety,
including `robot-name` and any robot-related root or close semantic family.
Do not use holdout wording, APIs, classes, fields, examples, tests, references,
or model outputs. Do not create a candidate by paraphrasing an online robot
simulator exercise.

Each candidate below must be independently authored and must materially differ
from every holdout in at least three dimensions, such as command vocabulary,
state model, world topology, collision/resource rules, returned result,
error/rollback policy, and visible C++ API. Run the repository's whole-slug
benchmark denylist and semantic contamination checks before admission. Reject
and backfill every near-match; do not weaken the checker.

## Online Material Status

Robot-simulation exercises are available online, but they are useful only for
private concept study or source discovery. They are not a drop-in SFT source
inventory: every external source needs explicit license and semantic
contamination review.

The following tasks materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `warehouse-wave-router` | Warehouse wave router | BFS over directed aisles with pick-capacity depot returns and unreachable-shelf accounting. |
| `greenhouse-moisture-controller` | Greenhouse moisture controller | Event-driven moisture decay plus deterministic longest-dry-run selection. |
| `drone-altitude-pathfinder` | Drone altitude pathfinder | Dijkstra over layered cell and remaining-battery states with recharge transitions. |
| `harbor-stack-rebalancer` | Harbor stack rebalancer | Atomic top-container moves between bounded stacks. |
| `mars-energy-route-planner` | Mars energy route planner | Weighted terrain Dijkstra with uphill costs, slope exclusion, and an energy budget. |
| `subway-switch-inspector` | Subway switch inspector | Traverse a directed rail graph under explicit branch-switch state. |
| `fire-spread-responder` | Fire spread responder | Double-buffer cellular fire propagation after bounded extinguish actions. |
| `orchard-capacity-harvester` | Orchard capacity harvester | Serpentine matrix traversal with an atomic capacity-stop rule. |
| `hospital-priority-courier` | Hospital priority courier | Manually maintained stable binary heap with sterile-zone filtering. |
| `ocean-dive-profiler` | Ocean dive profiler | Sequential depth-time validation with oxygen integration and decompression rules. |
| `construction-load-router` | Construction load router | Stateful graph traversal where road admission depends on current payload. |
| `library-label-sorter` | Library label sorter | Character-state label parsing, checksum validation, and stable category routing. |
| `factory-lockout-inspector` | Factory lockout inspector | Explicit lockout finite-state transition table with acknowledgement-gated reset. |
| `snowplow-edge-router` | Snowplow edge router | Deterministic Hierholzer traversal over directed road-edge identities. |
| `station-airlock-repair` | Station airlock repair | Pressure-gated airlock graph transitions with leak and repair-kit state. |
| `museum-tour-planner` | Museum tour planner | Repeated closure-aware weighted shortest-path legs. |
| `recycling-conveyor-controller` | Recycling conveyor controller | Simultaneous conveyor slot updates with typed terminal routing and latched jams. |
| `farm-pressure-irrigator` | Farm pressure irrigator | Difference-array range demand plus deterministic proportional pressure allocation. |
| `rescue-frontier-explorer` | Rescue frontier explorer | Weighted frontier search over cell and rubble-marker state. |
| `airport-taxiway-scheduler` | Airport taxiway scheduler | Earliest conflict-free interval reservations on undirected taxiway segments. |

## Materialization Requirements

Every root needs a task-specific C++17 public API and a different substantive
algorithm or state-transition mechanism. Changing only nouns, class names,
commands, coordinates, or resource fields is a blocking duplicate-family
failure. The v2 inventory deliberately spans graph search, event simulation,
stack mutation, lexical parsing, finite-state protocols, edge traversal,
interval scheduling, range allocation, and simultaneous cellular/pipeline
updates. No two roots may share a reference control-flow template.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- initial placement and task-specific world-boundary behavior;
- valid and invalid mode/orientation transitions;
- blocked moves with the exact no-state-mutation or rollback policy;
- resource depletion, recharge/refill, carrying capacity, and task completion;
- command-sequence execution, partial failure, and trace ordering;
- repeated commands, empty command streams, and malformed commands;
- multi-cell objects, terrain/route constraints, and world updates where
  applicable;
- randomized command sequences checked against an independent state-machine
  oracle;
- a final contamination screen proving the candidate remains outside all
  benchmark holdout families.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
