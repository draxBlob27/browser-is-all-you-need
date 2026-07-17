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
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

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
| `sim-warehouse-picker` | Warehouse picker | Execute pick, load, unload, and turn commands on a shelf map with carrying capacity. |
| `sim-greenhouse-cart` | Greenhouse cart | Traverse greenhouse lanes, water plots, avoid wet-floor cells, and manage water level. |
| `sim-drone-delivery` | Drone delivery | Fly between altitude layers, respect no-fly zones, consume battery, and return a flight trace. |
| `sim-harbor-crane` | Harbor crane | Move a crane on rails, lift/place containers, and enforce stack-height limits. |
| `sim-mars-rover-energy` | Mars rover energy | Navigate terrain with elevation costs, solar recharge cells, and blocked slopes. |
| `sim-subway-maintenance` | Subway maintenance cart | Move on connected track segments, switch rails, and inspect flagged sections. |
| `sim-firefighter-bot` | Firefighter bot | Navigate rooms, refill water, extinguish fires, and reject unsafe smoke-zone moves. |
| `sim-orchard-harvester` | Orchard harvester | Traverse rows, harvest ripe trees, avoid obstacles, and track bin capacity. |
| `sim-hospital-courier` | Hospital courier | Carry samples between departments while respecting sterile-zone and priority rules. |
| `sim-ocean-survey` | Ocean survey vehicle | Dive, surface, scan, and manage oxygen under depth-dependent movement rules. |
| `sim-construction-hauler` | Construction hauler | Collect materials, traverse weight-limited roads, and unload at designated sites. |
| `sim-library-sorter` | Library sorter | Move between return stations, scan books, route by category, and handle unreadable labels. |
| `sim-factory-inspector` | Factory inspector | Follow inspection routes, enter machine modes, record faults, and obey lockout states. |
| `sim-snowplow-route` | Snowplow route | Clear road cells, manage salt supply, and respect one-way streets and turn restrictions. |
| `sim-space-station-repair` | Space-station repair bot | Move through modules, seal leaks, consume repair kits, and manage airlock state. |
| `sim-museum-guide` | Museum guide | Lead a tour through rooms, react to closed exhibits, and record visited landmarks. |
| `sim-recycling-sorter` | Recycling sorter | Move conveyors, identify material bins, handle jams, and count sorted items. |
| `sim-farm-irrigator` | Farm irrigator | Position irrigation arms, open valves, enforce pressure limits, and report watered cells. |
| `sim-search-and-rescue` | Search-and-rescue rover | Explore a grid with rubble, deploy markers, rescue targets, and return status. |
| `sim-airport-tug` | Airport tug | Couple aircraft, route through taxiway constraints, and decouple at assigned gates. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a generic
robot coordinate/orientation class with only left/right/advance commands. The
typed world state, commands, resource rules, failure policy, trace/result type,
and edge cases must materially differ between roots.

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

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
