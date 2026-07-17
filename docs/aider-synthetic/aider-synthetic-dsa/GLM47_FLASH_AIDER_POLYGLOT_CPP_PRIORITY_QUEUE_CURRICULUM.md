# Priority Queue Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum targets priority-ordered storage: heap invariants, stable
tie-breaking, key updates, cancellation, bounded selection, and multi-queue
scheduling. It does **not** propose renamed copies of an online heap exercise.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Decontamination Boundary

The official Aider C++ benchmark holdout set remains excluded in its entirety.
Do not use any holdout wording, APIs, classes, field names, examples, tests,
references, or model outputs. Do not construct a candidate by paraphrasing an
online priority-queue exercise.

Each candidate below must be independently authored and materially differ from
all excluded roots in at least three dimensions: priority direction/key shape,
tie-break policy, update/cancellation behavior, resource/stream model, result
or diagnostic type, error policy, and visible C++ API. Run the repository's
whole-slug benchmark denylist and semantic contamination checks before
admission. Reject and backfill every near-match; do not weaken the checker.

## Online Material Status

Priority-queue problems are available online, but they are useful only for
private concept study or source discovery. They are not a drop-in SFT source
inventory: every external source needs explicit license and semantic
contamination review.

The following tasks materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `pq-emergency-dispatch` | Emergency dispatch | Prioritize incidents by severity, deadline, and arrival sequence; allow cancellation. |
| `pq-build-scheduler` | Build scheduler | Schedule build jobs by dependency-ready priority and estimated duration. |
| `pq-flight-standby` | Flight standby | Promote passengers by status, check-in time, and ticket sequence. |
| `pq-print-routing` | Print routing | Dispatch print jobs by urgency and page count with deterministic equal-priority order. |
| `pq-hospital-triage` | Hospital triage | Update patient acuity, remove discharged patients, and select the next patient. |
| `pq-network-retries` | Network retries | Pop earliest retry deadline, reschedule failed requests, and discard cancelled requests. |
| `pq-warehouse-picks` | Warehouse picks | Prioritize picks by shipping cutoff and walking-zone cost. |
| `pq-road-snowplows` | Snowplow dispatch | Assign road segments by hazard score and deadline, with priority changes after weather updates. |
| `pq-support-escalations` | Support escalations | Escalate tickets, lower resolved tickets, and retrieve the next SLA-risk case. |
| `pq-auction-orders` | Auction orders | Match best-priced orders with time-priority ties and cancel by order ID. |
| `pq-video-transcodes` | Video transcodes | Schedule transcodes by customer tier and remaining render cost under a worker limit. |
| `pq-data-backups` | Data backups | Select next backup by risk, age, and storage-size tie rules. |
| `pq-package-delivery` | Package delivery | Dispatch parcels by promised window and route zone while allowing address correction. |
| `pq-game-matchmaking` | Game matchmaking | Select waiting players by rating deviation and wait time with stale-entry removal. |
| `pq-memory-reclaimer` | Memory reclaimer | Reclaim cache blocks by reclaim score and age, skipping pinned blocks. |
| `pq-conference-talks` | Conference talks | Choose next talk setup by room readiness, speaker priority, and start deadline. |
| `pq-security-alerts` | Security alerts | Order alerts by risk score, asset criticality, and first-seen timestamp. |
| `pq-maintenance-crews` | Maintenance crews | Assign work orders by outage impact, skill match, and due time. |
| `pq-search-top-results` | Search top results | Maintain top-K scored result candidates with deterministic ID ties. |
| `pq-metric-anomalies` | Metric anomalies | Stream anomaly events and return the highest-priority unresolved anomalies. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose only a
generic `push`, `top`, and `pop` heap assignment. Include the priority key,
tie policy, handle/update/cancellation semantics, bounded-resource behavior,
and result/diagnostic type in the starter interface.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- empty queue, singleton queue, and equal-priority ties;
- min-heap/max-heap orientation under the declared task contract;
- insertion, removal, and stable tie-breaking;
- priority increase/decrease and cancellation by stable handle where exposed;
- stale heap records after an update and exact-once selection behavior;
- top-K boundary behavior, worker/resource limits, or merge behavior where
  applicable;
- invalid priority values and no-state-mutation failure handling;
- large adversarial update traces that distinguish intended logarithmic heap
  operations from repeated full sorting where a complexity goal is stated;
- randomized cases checked against a simple sorted-vector/reference oracle;
- a final contamination screen proving the candidate remains outside all
  benchmark holdout families.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
