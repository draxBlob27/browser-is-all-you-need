# Priority Queue Curriculum: Decontaminated Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum targets materially different priority mechanisms: indexed and
d-ary heaps, bounded top-K and double-ended heaps, bucket/radix/calendar
queues, meldable heap families, price levels, tournament trees, hierarchical
queue heads, lazy versioning, and weighted-fair scheduling. A shared binary
heap or linear scan hidden behind twenty domain names is explicitly invalid.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

The official Aider C++ benchmark holdout set remains excluded in its entirety.
Do not use any holdout wording, APIs, classes, field names, examples, tests,
references, or model outputs. Do not construct a candidate by paraphrasing an
online priority-queue exercise.

Each candidate below must be independently authored and materially differ from
every other family root in both logic and implementation, not merely in domain
names or method names. Distinct ordering nouns are insufficient: each retained
root owns the mechanism named in the table and a private discriminator rejects
the easiest generic substitute. Run the repository's whole-slug benchmark
denylist, semantic duplication, and core-mechanism checks before retaining a
root. Reject every near-match; do not weaken the checker.

## Online Material Status

Priority-queue problems are available online, but they are useful only for
private concept study or source discovery. They are not a drop-in SFT source
inventory: every external source needs explicit license and semantic
contamination review.

The following tasks materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## Proposed Decontaminated Tasks

| ID | Required mechanism | Distinguishing contract |
|---|---|---|
| `pq-emergency-dispatch` | Indexed binary max-heap | Mutable priority/cancellation repairs an ID-to-index map. |
| `pq-build-scheduler` | Four-ary ready heap | Dependency-blocked jobs enter a four-child heap only when ready. |
| `pq-flight-standby` | Tiered FIFO buckets | Versioned tier changes invalidate stale bucket tickets. |
| `pq-print-routing` | Weighted two-lane cycle | Two urgent FIFO dispatches alternate with one normal dispatch. |
| `pq-hospital-triage` | Aging acuity buckets | Waiting epochs promote patients through five bounded buckets. |
| `pq-network-retries` | Monotone radix heap | XOR-distance buckets redistribute at bit boundaries. |
| `pq-warehouse-picks` | Heap of zone heads | Only one FIFO head from each zone competes globally. |
| `pq-road-snowplows` | Pairing heap | District meld and two-pass delete-root use child/sibling links. |
| `pq-support-escalations` | Mutable leftist heap | Versioned escalation plus queue meld maintains stored null-path ranks. |
| `pq-auction-orders` | Price-level book | A price heap selects FIFO order deques and removes stale levels. |
| `pq-video-transcodes` | SRPT preemptive heap | A running slot and waiting min-heap form a preemption state machine. |
| `pq-data-backups` | Circular calendar queue | A bounded absolute-day horizon wraps through 32 FIFO buckets. |
| `pq-package-delivery` | Min-max heap | One alternating-level array supports minimum and maximum removal without duplicate heaps. |
| `pq-game-matchmaking` | Adjacent-gap candidate heap | A heap ranks only neighboring ratings and is rebuilt after matches. |
| `pq-memory-reclaimer` | Lazy versioned heap | Rescore and pin changes leave stale snapshots for root purging. |
| `pq-conference-talks` | Winner tournament tree | Fixed room leaves update only one ancestor path. |
| `pq-security-alerts` | Binomial heap | Feed union performs degree carries; bounded batch investigation repeatedly reconstitutes child forests by degree. |
| `pq-maintenance-crews` | Skill-partitioned indexed heaps | Each skill owns its own mutable heap; global filtered selection is invalid. |
| `pq-search-top-results` | Bounded top-K min-heap | The worst retained result is the root and noncompetitive inputs are discarded. |
| `pq-metric-anomalies` | Weighted-fair head heap | One FIFO head per stream competes by fixed-point virtual finish time. |

## Materialization Requirements

Every root needs a task-specific C++17 public API and an independently rendered
reference. Do not expose only generic `push`, `top`, and `pop`, and do not
factor the substantive implementation through a shared generic heap template.
The owner must reject standard heap adapters, full-collection sort/selection
substitutes, missing mechanism markers, duplicate semantic signatures, and a
pairwise normalized-token similarity at or above the family threshold.

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
- deterministic adversarial traces and representation checks appropriate to
  each mechanism;
- a deterministic, independent simple-value model for every root, covering
  every public mutation and selection class and comparing the return plus the
  complete observable removal order from a copied structure after every
  operation;
- one topic-specific bad substitute per root that executes and proves the
  expected rejection path rather than scanning the good reference for a token;
- a final contamination screen proving the candidate remains outside all
  benchmark holdout families.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.

## Owner and local status

The repository owner is
`src/w8_biayn/integrations/moonlight_priority_queue_aider_tasks.py`, with
mechanism-specific C++ contracts in the sibling
`moonlight_priority_queue_cases.py`. It preserves the legacy renamed-template
family and writes fresh roots only beneath
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/priority-queue/`. The strongest
status is recorded per root by the owner verifier. The family-designated locked
oracle is
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
with Docker network `none`; this curriculum itself does not claim
`local_family_verified`.
