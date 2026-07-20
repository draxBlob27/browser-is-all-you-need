# Table Pivot Remediation Curriculum

Status: derived from the current generated materialization manifest and Docker
receipt for the twenty v2 roots below. The withdrawn receipt
`sha256:c415a87b2050a7a0bbf2c1776420fd098d592ca1eff2ce6141bb654e5997cc66`
is preserved only as invalidated history, not evidence. This curriculum
follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with
`FAMILY_NAME=table-pivot` and
`FAMILY_TYPE=aider-text-grid-reshaping`. The immutable v1 template family stays
at `.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/table-pivot/`; the
owner writes only the parallel v2 tree at
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/table-pivot/`.

Use this with `docs/AIDER_SFT_SCOPE.md` and the normative audit at
`docs/aider-tasks-spec/aider-text-grid-reshaping/table-pivot.md`. These are
local clean-room task candidates. Dataset handoff is `not_requested`.

## Legacy finding and disposition rule

The twenty legacy roots share one `PivotBatch`/`PivotRow` map template and only
vary nouns, typed-unit literals, and reject/sum/last/max duplicate policies.
That is a semantic/template duplicate family, not twenty implementations.
Following the deterministic rule, the lexicographically first independently
salvageable root, `pivot-call-center`, is repaired in place. The other nineteen
legacy roots are replaced rather than retained through renaming.

## V2 capability inventory

| V2 task ID | Legacy root | Disposition | Observable capability and primary mechanism |
| --- | --- | --- | --- |
| `pivot-call-center` | `pivot-call-center` | repair-in-place | Agent/shift cross-tabulation with additive duplicates and earliest stable argmax. |
| `clinic-state-transition-grid` | `pivot-clinic-visits` | replace | Per-patient chronological state replay into a square transition matrix. |
| `venue-capacity-grid` | `pivot-community-events` | replace | Capacity-key join, additive allocation, and exact overflow rejection. |
| `depot-shortfall-table` | `pivot-emergency-supplies` | replace | Latest stock-check arbitration, target reconciliation, and deficit ordering. |
| `tiered-billing-pivot` | `pivot-energy-bills` | replace | Cumulative-read differencing followed by two-tier price projection. |
| `defect-pareto-matrix` | `pivot-factory-defects` | replace | Line/type cross-tabulation and stable cumulative Pareto ranking. |
| `seasonal-yield-delta` | `pivot-farm-harvests` | replace | Season alignment, adjacent signed deltas, and largest-decline selection. |
| `airport-delay-percentiles` | `pivot-flight-delays` | replace | Cell sample collection and nearest-rank percentile selection. |
| `room-occupancy-interval-grid` | `pivot-hotel-bookings` | replace | Half-open stay expansion with per-room collision detection. |
| `assay-weighted-mean-table` | `pivot-lab-results` | replace | Weighted numerator/denominator aggregation with explicit missing cells. |
| `branch-category-distinct-table` | `pivot-library-circulation` | replace | Cell-level distinct-title sets paired with additive loan totals. |
| `vendor-product-leader-table` | `pivot-market-sales` | replace | Revenue matrix construction and stable product-column argmax. |
| `exhibit-running-attendance` | `pivot-museum-tickets` | replace | Signed daily delta folding into nonnegative prefix attendance. |
| `orchard-score-band-table` | `pivot-orchard-inspections` | replace | Ordered threshold classification into block/band histograms. |
| `cohort-visit-retention` | `pivot-research-cohorts` | replace | Enrollment join, unique attendance bitmap, and baseline retention ratios. |
| `river-unit-normalized-table` | `pivot-river-quality` | replace | Base-to-milli conversion and per-cell minimum/maximum/spread reduction. |
| `student-letter-grade-table` | `pivot-school-grades` | replace | Latest-attempt arbitration and descending letter-band classification. |
| `solar-gap-interpolation-table` | `pivot-solar-output` | replace | Unique sparse pivot with bounded one-cell interpolation only. |
| `route-stop-cross-tab` | `pivot-transit-ridership` | replace | Route-path membership join with separate missing and off-route sentinels. |
| `warehouse-backlog-aging` | `pivot-warehouse-orders` | replace | FIFO demand-lot replay into day-end backlog age buckets. |

Every root fixes its own public C++17 API, owned state/algorithm, mutation or
selection rules, invalid/duplicate/absent/empty behavior, ordering and tie
rules, independent reference control flow, deterministic oracle, and executed
topic-specific false substitute. Remedy records and their complete
specifications live under the generated sibling `.state/remedy/` directory.

## Decontamination and diversity boundary

All official Aider Polyglot C++ roots remain permanent holdouts. The owner
normalizes emitted docs, public APIs, references, visible/private tests, and
false substitutes while neutralizing identifiers, literals, clean-room domain
nouns, and endpoint direction. It compares all 190 unordered v2 pairs and all
520 v2-to-holdout pairs. The production comparator also rejects a complete
domain/identifier-renamed clone, a constants/policy-only clone, and an
opposite-end-selection clone. Each is a complete coherent clone derived from
the emitted `pivot-call-center` root and screened through the exact same
seven-dimension extractor and production comparator; each control first passes
the same two normal and two sanitizer behavior tests.

## Materialization and evidence

```bash
bash examples/slime/moonlight_cpp_perf/prepare_table_pivot_aider_tasks.sh \
  --force --verify-core --docker-sanity
```

The current receipt is admissible only when the mandatory pinned image ran with
`--network none`. All twenty references
passed two clean normal and two fresh ASan/UBSan CTests, all twenty false
substitutes compiled and failed executed tests, and all three clone controls
passed runtime tests before semantic rejection. Exact family, mounted-tree,
owner, case, reference, negative, control, toolchain, and receipt hashes are
read from the current machine-readable receipt and are never inherited from a
prior forced generation.
Host verification is separately `not_completed` because host `cmake` is
unavailable; it is not substituted for Docker evidence.

## Completion boundary

All twenty roots reach `local_family_verified` only when the current
`docker_sanity` evidence reports it. The family has no separately designated locked grader, so
`locked_oracle` is false. This status creates no JSONL, token/mask evidence,
split, export, training authorization, dataset release, or benchmark-uplift
claim.
