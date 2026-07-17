# Coordinates, Moves, And Cross-Field Constraints Curriculum: Decontaminated Capability

Status: curriculum-design note. These are original concepts, not admitted SFT
roots or claims of online-dataset availability.

This curriculum separates lexical parsing from semantic agreement across fields:
bounds, ordering, occupancy, counts, and impossible-but-well-formed states. It
does not recreate a generic chess-move validator.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_VALIDATION_AND_INPUT_PARSING_TOPICS.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

Official Aider holdouts and all close semantic copies are excluded. Do not reuse
benchmark wording, APIs, examples, tests, references, or model outputs. Each
candidate must differ in at least three dimensions: setting, coordinate system,
state model, movement rule, public API, diagnostic result, and invalid-input
policy. Use the whole-slug denylist and semantic screen; reject and backfill any
near-match.

## Online Material Status

Online board-game and coordinate exercises are study/source-discovery material
only. Every C++17 root must be independently authored and reviewed.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `constraint-crane-yard-move` | Crane-yard move | Validate container coordinates and ensure a crane move does not cross blocked lanes. |
| `constraint-greenhouse-transfer` | Greenhouse transfer | Validate bed coordinates and plant moves against occupancy and cultivar-zone restrictions. |
| `constraint-robot-warehouse-step` | Robot warehouse step | Parse directional steps and reject moves outside the map or through reserved cells. |
| `constraint-canoe-portage-route` | Canoe portage route | Validate waypoint pairs, route order, and declared leg count. |
| `constraint-airfield-gate-swap` | Airfield gate swap | Validate gate assignments while rejecting duplicate aircraft and incompatible gate classes. |
| `constraint-theater-seat-relocation` | Theater seat relocation | Validate seat moves and require companion-seat rules for grouped reservations. |
| `constraint-orchard-sprayer-pass` | Orchard sprayer pass | Validate row/column passes against wind-direction and no-spray zone constraints. |
| `constraint-lab-plate-transfer` | Lab plate transfer | Validate source/destination wells and reject impossible volume or duplicate-transfer states. |
| `constraint-hiking-checkpoint-route` | Hiking checkpoint route | Validate checkpoint codes, monotonic route order, and declared total distance. |
| `constraint-factory-arm-command` | Factory arm command | Validate axis moves against bounds, collision envelopes, and mutually exclusive mode flags. |
| `constraint-marina-berth-assignment` | Marina berth assignment | Validate vessel/berth pairs against length, draft, and one-vessel occupancy. |
| `constraint-library-cart-sort` | Library cart sort | Validate shelf destinations and reject a cart order that violates required section order. |
| `constraint-volunteer-shift-swap` | Volunteer shift swap | Validate paired swaps with matching roles, non-overlap, and capacity constraints. |
| `constraint-delivery-locker-route` | Delivery locker route | Validate locker coordinates and sequence constraints for temperature-sensitive parcels. |
| `constraint-satellite-panel-command` | Satellite panel command | Validate panel indices and reject commands conflicting with current deployment state. |
| `constraint-aquarium-fish-transfer` | Aquarium fish transfer | Validate tank moves against capacity, species compatibility, and source counts. |
| `constraint-classroom-desk-layout` | Classroom desk layout | Validate desk coordinates and ensure accessibility paths remain connected. |
| `constraint-rail-switch-plan` | Rail switch plan | Validate switch settings and reject routes that create conflicting track occupancy. |
| `constraint-emergency-supply-drop` | Emergency supply drop | Validate grid drop points against bounds, exclusion zones, and declared package totals. |
| `constraint-solar-array-inspection` | Solar-array inspection | Validate panel coordinates and inspection sequence against adjacency and no-repeat rules. |

## Materialization Requirements

Use typed domain inputs and a domain result/error API, never a generic
`is_valid_move`. Define coordinate bases, bounds, equality rules, mutation
semantics, failure precedence, and whether validation is atomic. Hidden tests
must cover malformed tokens, boundary coordinates, duplicate identifiers,
contradictory flags, missing companions, exact capacity/order equality, and
randomized traces checked against a simple state oracle with no mutation on failure.

## Admission Boundary

Candidates require the standard licensing, provenance, oracle, sanitizer,
contamination, split-family, rendering, token/mask, and release verification gates.
