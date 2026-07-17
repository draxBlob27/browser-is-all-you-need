# Interval Scheduling Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum targets interval reasoning: overlap, containment, endpoint
policy, compatibility, weighted selection, resource allocation, and schedule
diagnostics. It does **not** propose renamed copies of any benchmark date,
calendar, or interval task.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

The official Aider C++ benchmark holdout set remains excluded in its entirety,
including date/time or scheduling-related roots such as `meetup` and all close
semantic families. Do not use holdout wording, APIs, classes, field names,
examples, tests, references, or model outputs. Do not construct a candidate by
paraphrasing an online scheduling exercise.

Each candidate below must be independently authored and materially differ from
every holdout in at least three dimensions: interval representation,
endpoint/clock policy, optimization objective, resource model, mutation/query
behavior, result/diagnostic type, and visible C++ API. Run the repository's
whole-slug benchmark denylist and semantic contamination checks before
admission. Reject and backfill every near-match; do not weaken the checker.

## Online Material Status

Interval-scheduling exercises are available online, but they are useful only
for private concept study or source discovery. They are not a drop-in SFT
source inventory: every external source needs explicit license and semantic
contamination review.

The following tasks materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `interval-operating-rooms` | Operating-room planner | Select the highest-value compatible surgeries with mandatory cleanup buffers. |
| `interval-delivery-windows` | Delivery-window planner | Maximize completed deliveries while honoring driver-specific availability intervals. |
| `interval-broadcast-lineup` | Broadcast lineup | Choose non-overlapping programs maximizing audience value with fixed transition gaps. |
| `interval-machine-maintenance` | Machine maintenance | Schedule maintenance jobs on one machine and return rejected-conflict diagnostics. |
| `interval-court-docket` | Court docket | Allocate hearings to courtrooms while minimizing rooms and preserving case priorities. |
| `interval-charging-stations` | Charging stations | Assign charging sessions to a limited number of plugs with earliest-finish tie rules. |
| `interval-field-bookings` | Field bookings | Accept, reject, cancel, and query sports-field reservations under half-open intervals. |
| `interval-freight-platforms` | Freight platforms | Compute minimum loading platforms and identify the conflicting freight intervals. |
| `interval-ad-campaigns` | Ad campaigns | Choose weighted advertisement slots subject to sponsor cooldown constraints. |
| `interval-shift-coverage` | Shift coverage | Select shifts that cover required periods with minimum cost and no worker overlap. |
| `interval-flight-gates` | Flight gates | Assign flight turnaround intervals to gates with compatibility and buffer rules. |
| `interval-warehouse-docks` | Warehouse docks | Book dock intervals, reschedule orders, and expose the earliest available slot. |
| `interval-road-closures` | Road closures | Merge overlapping closure windows and report affected route-duration spans. |
| `interval-sensor-outages` | Sensor outages | Classify overlapping outage intervals and calculate total downtime after union. |
| `interval-stream-recording` | Stream recording | Select recordings under storage budget, overlap rules, and program priorities. |
| `interval-conference-tracks` | Conference tracks | Partition talks into the fewest tracks and return deterministic track assignments. |
| `interval-patrol-routes` | Patrol routes | Choose compatible patrol intervals with travel-time-dependent gaps. |
| `interval-lease-audits` | Lease audits | Detect containment, improper overlap, and gap violations in lease periods. |
| `interval-rescue-dispatch` | Rescue dispatch | Allocate emergency teams to incidents while prioritizing deadlines and travel windows. |
| `interval-data-backups` | Data backups | Schedule non-overlapping backup jobs, allow predeclared maintenance blackouts, and return a conflict explanation. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose an unadorned
list of start/end pairs and ask whether intervals overlap. Include each task's
typed interval representation, endpoint convention, optimization/resource
rules, invalid-input behavior, and result/diagnostic type in the starter
interface.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- zero-length, touching, nested, identical, and disjoint intervals under the
  explicit open/closed/half-open endpoint policy;
- invalid or reversed endpoints and no-state-mutation behavior where mutable;
- equal finish-time, equal weight, and equal resource tie-breaking;
- required buffers, cooldowns, blackout periods, and travel gaps where
  applicable;
- cancellation, rescheduling, and query behavior for mutable schedulers;
- optimality or minimum-resource proofs on adversarial small instances;
- large boundary-heavy inputs that distinguish intended sorting/DP/sweep-line
  algorithms from repeated quadratic rescans where a complexity goal is stated;
- randomized cases checked against a brute-force or independent interval oracle;
- a final contamination screen proving the candidate remains outside all
  benchmark holdout families.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
