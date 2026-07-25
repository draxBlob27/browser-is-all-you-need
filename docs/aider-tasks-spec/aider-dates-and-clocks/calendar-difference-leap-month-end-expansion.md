# Calendar Difference, Leap, And Month-End Expansion Specification

## Identity and workflow

`TASK_FAMILY_ROOT` is
`.w8-biayn/data/aider-tasks-expansion-v1/time-date/calendar-difference-leap-month-end/`.
This is family `expansion-v1-calendar-difference-leap-month-end-v1`, a set of
90 clean-room `new-root` candidates for the binding count-plan cell. The owner,
focused test, curriculum, output root, and prompt paths are fixed by the
curriculum. The design phase uses `generate-family-spec.md`; after this
specification exists, implementation and verification use
`implement-family-for-sft.md`. These prompts are sequential phases, not
combined authorities.

All roots start with `primary_core_objective: not_achieved` before generation.
After generation, that field becomes `achieved` only when the emitted reference
contains the named core region and both the reference and its distinct
compiling false substitute are executed by the current normal and sanitizer
tests. Every root's disposition is `repair-in-place` during an actionable
creator/audit cycle; a collision or contamination finding changes the
disposition to `reject` or `replace` under `verify-and-remedy.md`.

## Public APIs and common behavior

All APIs are in `namespace curriculum` and use:

```cpp
struct Date {
    int year;
    int month;
    int day;
};
```

`Date` equality is field equality. Valid dates use years 1..9999 and Gregorian
month lengths. Metric roots declare one task-specific method returning
`std::optional<long long>` from an ordered `[first,last]` date pair. Transform
roots declare one task-specific method returning `std::optional<Date>` from a
date and integer parameter. Series roots declare one task-specific method
returning `std::optional<std::vector<Date>>` from an ordered date pair and
integer parameter.

An invalid date, reversed range, invalid parameter, or out-of-range result
returns `std::nullopt` without mutation. Empty series are valid. Series order
is chronological with no duplicate dates. Scalar arithmetic must remain in
signed 64-bit range. Ties are chronological. No root owns external state.
The prompt gives an example-independent observable rule for each row. Executed
properties cover 2024, the common-century 1900, the leap-century 2000,
equality, reversed and invalid inputs, parameter boundaries, and years 1 and
9999.

## Per-root objectives

Each row is a distinct observable objective. The named mechanism is required
in the emitted `CORE_BEGIN`/`CORE_END` region. The easiest false substitute is
the next row's mechanism within the same API group (wrapping at group end); it
must compile and fail the production tests.

Anchored schedule roots clamp per target month from the original anchor day,
never by propagating a previously clamped day forward: the clamped monthly
anchor emits day `min(parameter, month_capacity)` of every touched month, and
the quarterly anchor emits `first` advanced by 3, 6, 9, and further months with
the day of `first` clamped to each target month's capacity. The deterministic
Python oracle, the emitted reference, and the observable rule must agree on
these clamp semantics, and the visible and hidden executables must include
discriminating cases that reject clamp propagation. The rolled monthly anchor
oracle must stay total at the upper year range: a one-based offset from a month
origin that would leave years 1..9999 ends the schedule instead of raising.

| Task ID | API | Required core mechanism |
| --- | --- | --- |
| `calendar-signed-day-distance` | metric | signed ordinal subtraction |
| `calendar-weekday-cardinality` | metric | Monday-through-Friday span accumulation |
| `calendar-midpoint-ordinal` | metric | overflow-safe ordinal midpoint selection |
| `calendar-interior-day-cardinality` | metric | open-span cardinality |
| `calendar-crossed-month-boundaries` | metric | month-transition scan |
| `calendar-crossed-year-boundaries` | metric | year-transition scan |
| `calendar-contained-leap-days` | metric | leap-day membership scan |
| `calendar-contained-month-ends` | metric | month-end membership scan |
| `calendar-month-end-parity-balance` | metric | alternating month-end parity fold |
| `calendar-complete-months-between` | metric | clamped whole-month decomposition |
| `calendar-complete-years-between` | metric | anniversary whole-year decomposition |
| `calendar-thirty-day-convention` | metric | 30E/360 bounded difference |
| `calendar-actual-year-fraction` | metric | leap-aware annual fraction segmentation |
| `calendar-month-fragment-count` | metric | calendar-month partition counting |
| `calendar-year-fragment-count` | metric | calendar-year partition counting |
| `calendar-february-day-count` | metric | February membership accumulation |
| `calendar-long-month-day-count` | metric | 31-day-month membership accumulation |
| `calendar-month-capacity-transition-count` | metric | month-boundary capacity-change detection |
| `calendar-day-of-year-displacement` | metric | year-relative ordinal subtraction |
| `calendar-month-weighted-distance` | metric | month-index weighted span fold |
| `calendar-day-number-checksum` | metric | day-of-month span checksum |
| `calendar-leap-year-day-count` | metric | leap-year membership accumulation |
| `calendar-post-leap-pivot-day-count` | metric | post-February leap-year segment accumulation |
| `calendar-century-day-count` | metric | century boundary membership accumulation |
| `calendar-endpoint-month-length-delta` | metric | endpoint month-capacity comparison |
| `calendar-endpoint-month-residual-delta` | metric | endpoint residual-month displacement |
| `calendar-month-end-distance-sum` | metric | per-day residual-month fold |
| `calendar-triangular-day-load` | metric | per-day triangular position fold |
| `calendar-leap-cycle-index-delta` | metric | 400-year cycle coordinate difference |
| `calendar-boundary-density-score` | metric | weighted month/year/leap boundary density |
| `monthend-add-days` | transform | ordinal day displacement |
| `monthend-subtract-days` | transform | reverse ordinal displacement |
| `monthend-add-months-clamped` | transform | target-month day clamp |
| `monthend-add-months-rolled` | transform | overflow-day rollover |
| `monthend-add-months-eom-anchor` | transform | end-of-month anchor propagation |
| `monthend-add-years-clamped` | transform | February anniversary clamp |
| `monthend-add-years-march-shift` | transform | February anniversary March policy |
| `monthend-current-last-day` | transform | month-capacity projection |
| `monthend-next-boundary` | transform | strict forward month-end selection |
| `monthend-previous-boundary` | transform | strict reverse month-end selection |
| `monthend-nth-forward-boundary` | transform | iterated month-end stepping |
| `monthend-nth-reverse-boundary` | transform | reverse month-end stepping |
| `monthend-quarter-boundary` | transform | quarter terminal-month selection |
| `monthend-year-boundary` | transform | year terminal-day selection |
| `monthend-fiscal-boundary` | transform | parameterized fiscal terminal selection |
| `monthend-next-leap-day` | transform | strict forward leap-day search |
| `monthend-previous-leap-day` | transform | strict reverse leap-day search |
| `monthend-nth-leap-day` | transform | bounded leap-year enumeration |
| `monthend-clamp-requested-day` | transform | same-month requested-day clamp |
| `monthend-roll-requested-day` | transform | same-month overflow rollover |
| `monthend-reflect-day` | transform | month-capacity mirror selection |
| `monthend-month-end-offset` | transform | month-terminal reverse displacement |
| `monthend-next-month-start` | transform | strict forward month-origin selection |
| `monthend-quarter-start` | transform | quarter origin selection |
| `monthend-semester-boundary` | transform | half-year terminal selection |
| `monthend-next-smaller-month` | transform | forward month-capacity extremum search |
| `monthend-february-boundary` | transform | same-year February capacity selection |
| `monthend-century-cycle-clamp` | transform | hundred-year February clamp projection |
| `monthend-four-century-cycle` | transform | four-hundred-year exact-cycle projection |
| `monthend-ordinal-day-normalizer` | transform | year-relative ordinal normalization |
| `leapseries-month-end-partition` | series | closed-span month-end enumeration |
| `leapseries-month-start-partition` | series | closed-span month-origin enumeration |
| `leapseries-month-capacity-changes` | series | month-terminal capacity-transition enumeration |
| `leapseries-year-end-partition` | series | closed-span year-terminal enumeration |
| `leapseries-leap-day-partition` | series | closed-span leap-day enumeration |
| `leapseries-february-end-partition` | series | closed-span February terminal enumeration |
| `leapseries-clamped-monthly-anchor` | series | fixed requested-day monthly schedule |
| `leapseries-midmonth-monthly-anchor` | series | month-midpoint anchored schedule |
| `leapseries-rolled-monthly-anchor` | series | overflow-day monthly schedule |
| `leapseries-quarterly-anchor` | series | clamped three-month schedule |
| `leapseries-annual-clamped-anchor` | series | February-safe annual schedule |
| `leapseries-annual-march-anchor` | series | March-shift annual schedule |
| `leapseries-month-fragment-origins` | series | month-partition origin sequence |
| `leapseries-leap-status-run-starts` | series | maximal equal leap-status run origins |
| `leapseries-long-month-terminals` | series | 31-day-month terminal selection |
| `leapseries-leap-year-quarter-ends` | series | leap-year canonical quarter-terminal selection |
| `leapseries-century-exception-vector` | series | Gregorian century-exception enumeration |
| `leapseries-four-hundred-cycle-vector` | series | complete Gregorian-cycle enumeration |
| `leapseries-penultimate-month-days` | series | monthly penultimate-day selection |
| `leapseries-prime-month-days` | series | monthly prime-numbered-day selection |
| `leapseries-fiscal-end-partition` | series | parameterized fiscal terminal enumeration |
| `leapseries-capacity-run-starts` | series | maximal equal-capacity month-run origins |
| `leapseries-semester-end-partition` | series | half-year terminal enumeration |
| `leapseries-century-clamped-anchors` | series | hundred-year clamped anniversary sequence |
| `leapseries-leap-status-transitions` | series | annual leap-status transition anniversary sequence |
| `leapseries-quarter-start-partition` | series | canonical quarter-origin selection |
| `leapseries-leap-gap-midpoints` | series | consecutive leap-day midpoint selection |
| `leapseries-capacity-change-pairs` | series | month-capacity transition pair encoding |
| `leapseries-february-capacity-transitions` | series | February-capacity change-origin selection |
| `leapseries-calendar-cycle-checkpoints` | series | century and 400-year checkpoint merge |

## Starter, reference, tests, and roles

For every root, editable order is `<task-id>.h`, then `<task-id>.cpp`. The
starter header declares the complete API and the starter source returns
`std::nullopt`. `.meta/example.h` and `.meta/example.cpp` are complete private
replacements in the same order. The visible and private executables assert
multiple exact values, invalid/reversed behavior, parameter policy,
lower/upper range behavior, and, for series, exact elements plus chronological
uniqueness. The private executable covers both 1900 and 2000.
`.meta/negative_false_substitute.cpp` implements the
adjacent mechanism and `.meta/task_negative_test.cpp` is the same independent
private oracle; it must compile cleanly and exit nonzero.

Documentation and starters are prompt-visible. Tests, references, CMake,
provenance, test descriptions, controls, screens, receipts, and cycle state are
private. CMake is C++17, no extensions, `-Wall -Wextra -Wpedantic -Werror`,
offline, and discovers exactly `visible` and `hidden`.

## Docs register

Model-facing docs follow the official exercise documentation conventions.
Consistent with the official exercises that carry no introduction, roots in
this family omit `.docs/introduction.md` entirely. `.docs/instructions.md`
opens with `# Instructions`, names the API, states the mechanism as a natural
requirement together with the proleptic Gregorian rule and the observable
rule, and shows one concrete worked example under `## Example` whose values
match the visible check. Harness vocabulary (clean-room, task, benchmark,
oracle, generator, grader, hidden test, prompt, model, core mechanism, and
similar) never appears in `.docs`; test-coverage summaries are not part of
the instructions.

## Invariants and forbidden substitutes

The private Gregorian support invariant is round-trip preservation for every
validated civil date and correct month capacity under the 4/100/400 rule. The
per-root core invariant is the table's exact metric, transformation, or series
selection. Forbidden substitutes are platform date/time facilities, a
divisible-by-four-only leap rule, an adjacent endpoint/clamp/roll policy,
precomputed examples, and hard-coded output. Series roots additionally forbid
unsorted or duplicate output.

## Family, contamination, and oracle acceptance

The owner must compare all 4,005 retained pairs in seven separately recorded
artifact-derived dimensions plus deterministic observable boundary signatures;
execute the three coherent clone controls; compare
every candidate with all roots in both existing trees; and compare docs, API,
reference, and tests with all 26 official holdouts. Any collision or near-match
is rejected or replaced, never renamed.

The repository-pinned C++ image runs with `--network none`. Normal and a fresh
ASan/UBSan configuration must each discover and pass exactly two tests for all
90 references, while each false substitute compiles and exits nonzero. The
receipt binds owner, curriculum, spec, focused test, selected manifest, every
per-root role, image ID, compiler path/version/binary hash, CMake version,
commands, network policy, normalizer/policy hash, source and holdout inventory
digests, family/lineage/benchmark screens, and prompt hashes.

When Docker is unavailable, the owner's `--verify-host` mode runs the same
protocol on the documented host toolchain (clean normal plus fresh ASan/UBSan
builds of every reference and every hard-rule control, exactly two discovered
tests per mode, executed negative-fixture rejection) and writes
`.state/host-verify-receipt.json` bound to the current tree, owner, compiler,
and CMake identities. Host evidence is `host_verify`, never `locked_oracle`,
and does not by itself satisfy the mandatory Docker sanity gate.

Stable failure codes are `unsafe_output_root`, `unsafe_output_symlink`,
`duplicate_task`, `duplicate_family`, `benchmark_content_overlap`,
`generator_output_drift`, `unsafe_path`, `prompt_contract_incomplete`,
`invariant_not_enforced`, `adversarial_clone_not_rejected`,
`test_discovery_failed`, `reference_tests_failed`,
`docker_sanity_failed`, and `stale_receipt`.

## Ordered implementation and acceptance

1. Freeze both existing inventories and all 90 new-root lineages.
2. Materialize only through the owner into a fresh expansion-v1 family.
3. Run focused structural tests and deterministic owner regeneration.
4. Validate prompt/answer roles and execute every negative discriminator.
5. Recompute the 4,005-pair seven-dimension matrix and three clone controls.
6. Run existing-tree semantic lineage and official-holdout contamination screens.
7. Run network-disabled Docker normal and fresh ASan/UBSan verification.
8. Freeze the creator audit subject and hand raw evidence to an independent,
   read-only audit.
9. Preserve and remediate every finding through the owner, regenerate, and
   require a fresh audit before `local_family_verified`.

Dataset handoff is `not_requested`. This specification creates no JSONL,
release, training authorization, model response, evaluation, or uplift claim.
