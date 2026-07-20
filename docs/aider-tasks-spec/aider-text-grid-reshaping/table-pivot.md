# Table Pivot Family Remediation Specification

## Scope and immutable inputs

This audit follows `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`
with `FAMILY_NAME=table-pivot` and
`FAMILY_TYPE=aider-text-grid-reshaping`. Review date: 2026-07-18. The legacy
20-root family at
`.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/table-pivot/` is immutable.
The owner writes v2 artifacts only beneath
`.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/table-pivot/`.
This is local clean-room remediation; dataset handoff is `not_requested`.

The machine-readable status is derived only from the current generated
`.state/materialization-manifest.json` and `.state/docker-sanity.json`. The
earlier receipt
`sha256:c415a87b2050a7a0bbf2c1776420fd098d592ca1eff2ce6141bb654e5997cc66`
was invalidated: its controls used a control-only feature mapping, its policy
control changed labels rather than policy, and its tests did not independently
recompute every dimension decision. The owner preserves that withdrawal under
`.state/invalidated/`; this document does not treat the old receipt as proof.

The owner is
`src/w8_biayn/integrations/moonlight_table_pivot_aider_tasks.py`; its distinct
case inventory is
`src/w8_biayn/integrations/moonlight_table_pivot_cases.py`; focused coverage is
`tests/test_moonlight_table_pivot_aider_tasks.py`. Every legacy root is bound by
its exact pre-change tree hash in the owner-generated
`.state/remedy/<task-id>.json` record. The locally bound benchmark inventory is
the 26-root C++ tree at
`.cache/upstreams/aider-polyglot/cpp/exercises/practice/`.

The pre-change owner source was an untracked workspace file and has no Git
blob. Remedy `generator_revision` therefore truthfully binds the immutable
legacy family evidence-tree hash
`sha256:5f9be13006a512c6b4ef09efe7099ab45e9b81125250c928d8fb0911cdc66a9f`;
every record separately binds its exact legacy root hash. No unavailable
source revision is fabricated.

## Audit findings

### TP-F1 — One generic pivot template substitutes for twenty objectives

**Severity:** major

**Scope:** all 20 legacy roots

**Observed evidence:** every legacy reference uses the same `PivotBatch`,
`PivotRow`, header-index map, identity map, missing bitmap, and row-total loop.
Only class/method/domain names, one unit string, and duplicate policy vary.

**Why it matters:** the family implements one generic dense table fold rather
than the twenty advertised domain mechanisms.

**Root cause:** the legacy owner rendered one parameterized `_reference`
function for all curriculum rows.

**Remedy:** repair the lexicographically first independently salvageable root,
`pivot-call-center`, and replace the remaining nineteen roots with distinct
APIs, control flow, boundary rules, oracles, and false substitutes.

**Verification after remedy:** owner `--verify-core` must pass every one of the
190 seven-axis comparisons.

**Status:** resolved and reverified.

### TP-F7 — The first v2 hard-rule reverification was circular

**Severity:** blocker

**Scope:** the withdrawn v2 family claim and all three adversarial controls

**Observed evidence:** the first receipt's control screen manually assembled
asymmetric features instead of calling the exact emitted-artifact extractor.
Its constants control changed only visible labels, its opposite-end control did
not update the written contract, and focused tests trusted aggregate comparator
results instead of recomputing all 1,330 pair/dimension decisions.

**Why it matters:** runtime-passing but incoherent controls and circular tests
cannot prove the mandatory all-seven-dimensions hard rule.

**Root cause:** control construction and verification were added as a parallel
path rather than treated as complete generated task roots.

**Remedy:** force regeneration first archives and invalidates any terminal
claim. Each control is then derived from the emitted `pivot-call-center` root,
changes a nonempty declared file set coherently, retains a buildable full task
layout, and is loaded through `_artifact_dimensions` and rejected by the exact
production comparator. Focused tests independently enumerate the exact 20
roots and 190 pairs, recompute all seven decisions per pair from emitted bytes,
and independently inspect every control mutation and rejection dimension.

**Verification after remedy:** only a new exact-tree Docker receipt with all
root/reference/negative hashes, control hashes and changed files, mounted tree
hash, immutable image, network policy, compiler binary hash/version, CMake
version, normal/fresh-sanitizer counts, and negative rejection may restore
`local_family_verified`.

**Status:** resolved only when the current machine-readable receipt reports
`local_family_verified`; the withdrawn receipt remains invalid evidence.

### TP-F2 — Policy and noun changes create semantic duplicates

**Severity:** major

**Scope:** all 20 legacy roots

**Observed evidence:** normalized references collapse into four branches:
reject, sum, last, and maximum. Roots within a branch differ only by names and
literals; branches differ only in duplicate-cell assignment.

**Why it matters:** identifiers, raw hashes, and opposite merge policies do not
establish logic-and-implementation diversity.

**Root cause:** the legacy inventory treated domain names and policy values as
independent task design.

**Remedy:** v2 uses twenty mechanisms and derives public API, owned
state/algorithm, mutation/selection, invalid/boundary, reference control flow,
deterministic oracle, and topic-negative evidence from emitted artifacts.

**Verification after remedy:** the production comparator must pass all 190
candidate pairs and reject domain/identifier-renamed, constants/policy-only,
and opposite-end-selection controls.

**Status:** resolved and reverified.

### TP-F3 — Published objectives and generated contracts diverge

**Severity:** major

**Scope:** all legacy roots

**Observed evidence:** the curriculum promises transitions, capacity,
retention, occupancy, billing, interpolation, and other domain behaviors, but
every generated API returns the same row/column/value/missing/total report.

**Why it matters:** the prompt-visible contract does not teach the claimed
capability.

**Root cause:** proposed one-line curriculum ideas were never promoted into
complete per-root specifications.

**Remedy:** each generated remedy specification fixes a complete C++17 API,
valid/invalid/duplicate/absent/empty behavior, ordering, tie and arithmetic
rules, independent reference, and negative fixture.

**Verification after remedy:** exact prompt/role/reference checks plus focused
tests.

**Status:** resolved and reverified.

### TP-F4 — Legacy oracle evidence is host-only and unbound

**Severity:** blocker

**Scope:** all 20 legacy roots

**Observed evidence:** legacy `--verify` performs host CMake work but produces
no immutable-image, network-disabled, owner/tree/reference-bound receipt and no
explicit equal positive discovery proof.

**Why it matters:** host builds cannot establish mandatory Docker sanity or
`local_family_verified`.

**Root cause:** the legacy owner predates the current receipt contract.

**Remedy:** use the pinned C++ sanity image, `--network none`, explicit
`Unix Makefiles`, clean normal and fresh ASan/UBSan builds, positive equal test
counts, owner/tree/reference/negative hashes, and an owner-written receipt.

**Verification after remedy:** `--docker-sanity` must report two normal and two
sanitizer tests for every root with exact live tree and owner hashes.

**Status:** resolved and reverified. Host iteration remains `not_completed`
because host `cmake` is unavailable; `.state/host-verification-receipt.json`
records the exact blocked command and prerequisite. Mandatory Docker evidence
passed.

### TP-F5 — No executed false-substitute evidence

**Severity:** major

**Scope:** all 20 legacy roots

**Observed evidence:** legacy tests execute only the reference and never build
a plausible incorrect mechanism.

**Why it matters:** examples cannot distinguish the claimed algorithm from a
template, wrong tie rule, incorrect aggregation, reversed bound, or invalid
state transition.

**Root cause:** negative fixtures were absent from the owner and grader.

**Remedy:** each v2 root emits a strict-warning-clean
`.meta/negative_false_substitute.cpp`; it must build under the same flags and
be rejected by executed visible/private tests.

**Verification after remedy:** the Docker receipt must account for all twenty
compiled and rejected negatives.

**Status:** resolved and reverified.

### TP-F6 — Benchmark and family screens were claims, not evidence

**Severity:** major

**Scope:** all 20 legacy roots

**Observed evidence:** provenance states benchmark separation, but no bound
26-root semantic inventory or complete all-pairs family matrix existed.

**Why it matters:** names alone do not exclude semantic contamination or
duplicates.

**Root cause:** the legacy owner had no artifact-derived semantic screen.

**Remedy:** v2 compares emitted docs, APIs, references, visible/private tests,
and negatives across 190 family pairs and 520 official-holdout pairs using
`table-pivot-v2-identifier-literal-endpoint-neutral-7gram`.

**Verification after remedy:** `--verify-core` must record the exact comparison
counts and fail closed on `duplicate_family` or `benchmark_content_overlap`.

**Status:** resolved and reverified.

## Per-root accounting

| Legacy root | Legacy tree hash | Disposition | V2 root and primary mechanism |
| --- | --- | --- | --- |
| `pivot-call-center` | `sha256:b20f8bc975b0d000b20b3f1491a25ecf190cdfe59672d8d5ba457ba7f4279e32` | repair-in-place | `pivot-call-center`: additive cross-tab plus earliest argmax |
| `pivot-clinic-visits` | `sha256:50c77776397998143c8cb9d1ab0c67db9d2216b3bcab1decebf4c8823b453cea` | replace | `clinic-state-transition-grid`: chronological transition matrix |
| `pivot-community-events` | `sha256:5e4f699dbdf0107cbebd3e739d8d831f78bb911529e9952cbe1dde1891618d00` | replace | `venue-capacity-grid`: capacity-key join and overflow rejection |
| `pivot-emergency-supplies` | `sha256:a5ec0338441414538da1b7b8ccce1b000690c945bc828435b95dfd6423d66fab` | replace | `depot-shortfall-table`: latest-check reconciliation and deficit rank |
| `pivot-energy-bills` | `sha256:bc5130d5455c465ad1771330a91d161081a69b4238529c9b73e0c2a339c4b09f` | replace | `tiered-billing-pivot`: cumulative differencing and tier pricing |
| `pivot-factory-defects` | `sha256:46adb1bf901800c811db7e56c4e1014f4ea22c0348b15142bf328d80dea5732d` | replace | `defect-pareto-matrix`: cross-tab plus cumulative Pareto scan |
| `pivot-farm-harvests` | `sha256:f036fbb51b1ff63b5ab6a146fd1741aea75d43e86d011f28ca8ecbad19db3c0b` | replace | `seasonal-yield-delta`: adjacent differencing and decline selection |
| `pivot-flight-delays` | `sha256:28fd6d63a4bc64d29105219fcd2eecf3d0d61aa3e9c763d225facd8b57ea6272` | replace | `airport-delay-percentiles`: cell-wise nearest-rank selection |
| `pivot-hotel-bookings` | `sha256:12175e4751f6baad7db11423f21d741253ad8de12424071d18d61964add56f88` | replace | `room-occupancy-interval-grid`: half-open interval expansion |
| `pivot-lab-results` | `sha256:2a1f0d7b24db2d2cec70635edeccc6a4743e82479cc17ead9bbf5bd586acd58f` | replace | `assay-weighted-mean-table`: weighted numerator/denominator reduction |
| `pivot-library-circulation` | `sha256:5d3386f96d5d8f845c6da22f450e8f25dbdd06d762650530baed3f184c96738c` | replace | `branch-category-distinct-table`: cell set cardinality plus totals |
| `pivot-market-sales` | `sha256:4ff5bce24bfb4bb66feae8928b7b7485142258e1e9598268566de38f615368b8` | replace | `vendor-product-leader-table`: revenue fold plus stable column argmax |
| `pivot-museum-tickets` | `sha256:22b6ac31fe2680e008e3de263d584b1ea73b20b5d817948deac0a915d24a1817` | replace | `exhibit-running-attendance`: signed delta prefix accumulation |
| `pivot-orchard-inspections` | `sha256:5d6e87e9db309201e65f5cf9d2c84876b34608ced926010d5adc70b91f5a25fa` | replace | `orchard-score-band-table`: threshold classification histogram |
| `pivot-research-cohorts` | `sha256:cb743ad4af1fec034d8e169d9d1ccc63b6468c6955a5735b1dcf9752795ae49e` | replace | `cohort-visit-retention`: enrollment join and baseline normalization |
| `pivot-river-quality` | `sha256:516c9115c0c191135678de1ef65e68f1f348c25c81cb1fe938b100b695c0bd6d` | replace | `river-unit-normalized-table`: unit conversion and extremum ranges |
| `pivot-school-grades` | `sha256:18777fdc5ce9a5c94e6c1f472e6972d4ca5524025d9e473f352ba60434537516` | replace | `student-letter-grade-table`: latest-attempt arbitration and bands |
| `pivot-solar-output` | `sha256:545ca08cb415ca1a6aba565ed96e5326fd13875fb35cc316ea478a5fb57c2950` | replace | `solar-gap-interpolation-table`: bounded single-gap interpolation |
| `pivot-transit-ridership` | `sha256:960b0662c80d808ecbd7d8b20d1c8504bbc30f72f8da45dc029e9414cf58e506` | replace | `route-stop-cross-tab`: path membership and off-route sentinel projection |
| `pivot-warehouse-orders` | `sha256:fe83e1939d7b33dbaa97e4be5e29cf4e5b6ca574c228d7957e3bd537fdc9c290` | replace | `warehouse-backlog-aging`: FIFO lot replay and age buckets |

Exact after-tree hashes live in the corresponding remedy records and current
machine-readable receipt. No historical tree hash is promoted across forced
regeneration.

## Structural and evidence matrix

| Gate | Legacy result | V2 result |
| --- | --- | --- |
| Primary core objective | not achieved: one generic template | achieved: twenty named mechanisms and executed discriminators |
| Prompt boundary | structurally plausible | exact docs plus two editable task-named files only |
| Reference mapping | present | exact suffix mapping for both editable files |
| Family diversity | fail: noun/policy duplicates | pass: 190 seven-axis decisions plus three controls |
| Benchmark screen | unbound prose claim | pass: 520 comparisons against 26 bound holdouts |
| Normal/sanitizer | unreceipted host run | pass: 2+2 tests per root in pinned Docker image |
| Negative fixtures | absent | pass: 20 compile and fail executed tests |
| Clone runtime | absent | pass: three controls pass 2+2 tests then fail semantic screen |
| Dataset handoff | not authorized | `not_requested` |

## Commands and exact results

```bash
UV_CACHE_DIR=/tmp/uv-table-pivot-cache uv run pytest -q \
  tests/test_moonlight_table_pivot_aider_tasks.py
UV_CACHE_DIR=/tmp/uv-table-pivot-cache \
  bash examples/slime/moonlight_cpp_perf/prepare_table_pivot_aider_tasks.sh \
    --force --verify-core --docker-sanity
UV_CACHE_DIR=/tmp/uv-table-pivot-cache \
  bash examples/slime/moonlight_cpp_perf/prepare_table_pivot_aider_tasks.sh \
    --verify
```

Required focused result: all focused tests pass while independently checking
20 roots, 190 pairs, and all 1,330 per-dimension decisions. Required core
result: 20 roots, 190 passing family pairs, three coherent behavior-passing
clone controls rejected as `duplicate_family`, and 520 passing comparisons
against 26 official holdouts.

Host result: `not_completed`; host `cmake` is unavailable. The exact blocked
command and `missing_prerequisites: ["cmake"]` are recorded in
`.state/host-verification-receipt.json`.

The current Docker receipt is authoritative only when it reports pass in
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`
with network `none`. Every root passed 2 normal plus 2 fresh ASan/UBSan CTests;
every false substitute compiled and was rejected. Each clone control passed 2
normal plus 2 sanitizer tests before semantic rejection. Exact owner, case,
tree, per-reference, per-negative, control, toolchain, and receipt hashes are
read from that current receipt rather than copied into this prose.

## Conclusion

`primary_core_objective: achieved` for all twenty v2 roots. Prompt/role and
reference mapping, mandatory Docker oracle, executed negative fixtures,
all-pairs family diversity, and bound benchmark contamination screens pass.
Every root reaches `local_family_verified` only when the current
`docker_sanity` evidence says so;
`locked_oracle` is false because this family has no separately designated
locked grader. This is not a dataset release, SFT row, training authorization,
or benchmark-uplift claim.
