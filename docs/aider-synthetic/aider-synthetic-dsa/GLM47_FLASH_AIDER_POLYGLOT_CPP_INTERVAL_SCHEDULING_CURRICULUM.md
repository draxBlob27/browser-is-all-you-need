# Interval Scheduling Curriculum: Decontaminated Capability

Status: v2 local-family remediation curriculum. The legacy four-template family
is preserved under `.w8-biayn/data/aider-tasks/`; the owner materializes only
the parallel v2 re-verification family. This document does not claim dataset
admission or benchmark uplift.

This curriculum targets interval reasoning: overlap, containment, endpoint
policy, compatibility, weighted selection, resource allocation, and schedule
diagnostics. It does **not** propose renamed copies of any benchmark date,
calendar, or interval task.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

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

The legacy 20-root materialization advertised many domain rules but implemented
only four shared references: weighted selection, resource allocation, interval
union audit, and a mutable reservation ledger. Driver availability, storage
budgets, deadlines, travel matrices, cyclic endpoints, containment, set cover,
and other named rules were absent. Renaming those templates is not a remedy.

The v2 family therefore replaces every legacy root one-for-one with a distinct
C++17 API and a distinct substantive algorithm. No two rows share an algorithm
kind, public declaration set, state model, reference marker, or adversarial
negative fixture.

## Proposed Decontaminated Tasks

| V2 ID | Primary algorithm | Visible contract |
|---|---|---|
| `surgery-value-plan-v2` | predecessor-indexed weighted interval DP | Maximize surgery value with per-job cleanup. |
| `delivery-route-cover-v2` | farthest-reach greedy cover | Cover a route with the fewest windows. |
| `broadcast-break-stab-v2` | right-endpoint minimum stabbing | Place the fewest instants hitting closed program intervals. |
| `maintenance-throughput-order-v2` | Moore-Hodgson heap | Keep the most jobs meeting individual deadlines. |
| `docket-lateness-order-v2` | earliest-due-date sequencing | Minimize maximum hearing lateness. |
| `charging-priority-admission-v2` | capacity sweep with priority eviction | Retain higher-priority sessions under plug capacity. |
| `field-reservation-ledger-v2` | dual ordered mutable indexes | Book, cancel, and atomically reschedule reservations. |
| `freight-platform-peak-v2` | event sweep with active witness set | Report earliest peak occupancy and exact active IDs. |
| `campaign-budget-selection-v2` | budget-by-predecessor 2-D DP | Maximize compatible value under spend. |
| `shift-cost-cover-v2` | coordinate-DAG minimum-cost cover | Cover a target interval at minimum cost. |
| `flight-gate-partition-v2` | busy/free heap interval partitioning | Produce the minimum deterministic gate assignment. |
| `dock-common-free-slot-v2` | multi-calendar cursor intersection | Find the earliest slot free in every calendar. |
| `road-closure-complement-v2` | clipped union plus complement | Return canonical closed and open route segments. |
| `sensor-k-outage-duration-v2` | level-delta k-coverage sweep | Measure maximal spans with at least k outages. |
| `recording-conflict-components-v2` | active sweep plus disjoint-set union | Compute transitive overlap components. |
| `conference-containment-forest-v2` | strict-containment stack | Build immediate parent relationships and reject crossings. |
| `patrol-travel-chain-v2` | directed travel-compatibility DAG DP | Maximize a route-dependent patrol chain. |
| `lease-cyclic-normalization-v2` | split/merge/rejoin cyclic arcs | Canonicalize weekly leases that wrap. |
| `rescue-team-matching-v2` | augmenting-path bipartite matching | Maximize compatible incident/team assignments. |
| `backup-checkpoint-cover-v2` | bounded bitmask set-cover DP | Cover checkpoint instants with the fewest windows. |

## Materialization Requirements

Every root needs its row-specific C++17 API, owned state or algorithm, endpoint
policy, invalid-input behavior, result type, deterministic tie policy, and a
complete compilable private false substitute that embodies its named easiest
mistake. The verifier must build that substitute and then observe a positive
CTest failure count; comments, markers, grep, and source-presence checks are
not discriminator evidence. Shared use of sorting or vectors is incidental;
it cannot replace the advertised DP, heap, sweep, ordered-index, DSU, stack,
cyclic, matching, or set-cover mechanism.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Across the family, hidden tests must cover:

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
- independently derived direct-value or bounded exhaustive expectations for
  every behavior-only root, plus an independent vector model checked after
  every operation in the mutable-ledger trace;
- a final contamination screen proving the candidate remains outside all
  benchmark holdout families.

The family screen uses `interval-family-semantic-v3`: it noun-normalizes actual
documentation, public declarations, reference control flow, and test
assertions, checks all 190 candidate pairs, and checks all 520 candidate versus
official-holdout pairs from the pinned 26-root C++ checkout. Only the two
shared Catch support paths may be excluded, and their exact digests are part of
the semantic-screen receipt.

Materialize and verify only the parallel root:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_interval_scheduling_aider_tasks.sh \
  --force --verify-core --verify
```

The normative per-root remedies and evidence records live under the parallel
root's `.state/remedy/` directory. The checked-in audit is
`docs/aider-tasks-spec/aider-dsa/interval-scheduling.md`.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
