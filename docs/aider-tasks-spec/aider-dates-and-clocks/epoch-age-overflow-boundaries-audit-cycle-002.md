# Epoch, Age, And Overflow Boundaries — Independent Audit Cycle 002

Audit date: 2026-07-22

Status: `not_completed`

Decision: **zero of 80 roots are retained as verified candidates**. Five roots
have disposition `replace`; the other 75 have disposition
`repair-and-reverify`. The recorded creator preflight is structurally current,
but the family does not pass strict compilation, sanitizer, executable-contract,
hard-diversity, or inventory-bound semantic-screen gates.

## Confirmed Counts, Risks, And Next Gate

- Materialized roots: 80 unique selected IDs, 20 in each of four curriculum
  groups.
- Structurally valid roots: 80. Each has the exact 11-file family shape, one
  editable header, one private replacement, two declared test files, and safe,
  disjoint relative role paths.
- Verified retained roots: 0.
- Recorded Docker executions: 80 normal references, 80 sanitizer references,
  80 compiling negative fixtures, and three controls, each with two discovered
  tests per mode. These executions are **not accepted sanitizer or strict-build
  evidence** for the reasons in AEO-C02-F002 and AEO-C02-F003.
- Recorded family pairs: 3,160 with seven recorded dimensions. This is **not
  accepted diversity evidence** because the evaluator retains renamed
  identifiers, uses a different threshold for controls, and admits concrete
  constants/policy clones (AEO-C02-F001).
- Unresolved hard-gate findings: five. Cycle-001 findings AEO-C01-F001 through
  AEO-C01-F005 are not closed by the cycle-002 remedy records.
- Next gate: route AEO-C02-F001 through AEO-C02-F005 through
  `aider-task-family-remediation`, replace the five clone roots with five
  materially new contracts, repair the owner/scaffold/references/tests, freeze
  the current three-tree inventory, regenerate all 80 roots, rerun strict
  network-disabled normal plus halt-on-UB ASan/UBSan and negative/control
  checks, and submit that exact tree to audit cycle 003.

No SFT projection, dataset release, split, training authorization, or benchmark
uplift follows from this report.

## Frozen Audit Subject

- Family root:
  `.w8-biayn/data/aider-tasks-expansion-v1/aider-dates-and-clocks/epoch-age-overflow-boundaries/`
- Retained-task tree SHA-256, excluding `.state`:
  `ce101d1acce07c6c19ba3d4d5abccc6d46abba97dd394c8c07f2220099c41c8a`
- Owner SHA-256:
  `1c65bdeae90ecbbb7824048457d5082c68caa6aea7a1d755d41d069a1581ece6`
- Task-specific renderer SHA-256:
  `6d9276688403d48293272f35013ae54711e6b73d120842cd1568c2255f80e87d`
- Curriculum SHA-256:
  `3c3729835b575e1594fb77ef29b6a5a69eb5c2827e41cb5bdfce0b2be19a4576`
- Family-screen SHA-256:
  `8a92b724eff6a9a4ec6fccca2b38a6a2606c1884f3fff518e90882c48fba0a3c`
- Docker-receipt SHA-256:
  `a680d19ff7e017e0b10dc005e933dea21f696974448ac969c87e7e8bf2eaea85`
- Creator-preflight SHA-256:
  `aac62fcc521c9cee65bd059f0913ff283065fbdbcba657372edc36a2be6b312d`
- Current expansion sorted-root inventory SHA-256:
  `ed9f3665681d09a81749030d00d968c1a9895eb71037fc491149c6f5bc64b1ed`
- Audit-subject SHA-256:
  `28764ed444f266e1d5f6ef63cd727cf69a0b240647049a2670bb1669b5e23a2b`

The audit-subject hash is SHA-256 of the exact UTF-8 lines
`tree_sha256=...`, `owner_sha256=...`, `renderer_sha256=...`,
`curriculum_sha256=...`, `family_screen_sha256=...`,
`docker_receipt_sha256=...`, `creator_preflight_sha256=...`, and
`current_expansion_inventory_sha256=...`, in that order, each terminated by
one newline.

The subject has 80 unique public-prompt hashes, 80 unique reference hashes, and
80 unique hidden-test hashes. It has no symlinks or multiply linked files. The
80 cycle-001 IDs are absent from the materialized selected roots; every new
provenance record identifies a unique `replaces_task_id`. All 80 cycle-002
remedy records reconcile their root/reference/visible-test/hidden-test/negative
hashes to the live tree.

## Behavior Contract

The model must implement one exact C++17 whole-file header replacement from
the visible introduction, complete instructions, and starter only. Private
references, visible/private tests, CMake, provenance, negative fixtures, and
receipts must remain outside the prompt. Every root must implement its named
epoch, age, large-range, or rollover mechanism with defined integer arithmetic,
documented invalid/boundary behavior, deterministic tests, a compiling coherent
wrong substitute that is rejected, strict warnings, and clean normal plus fresh
ASan/UBSan execution.

Every retained pair must differ materially in all seven mandatory dimensions
after comments, strings, literals, identifiers, and clean-room domain nouns are
removed. Constants-only, policy-only, opposite-end, and domain/identifier
renames are not distinct roots. The same semantic policy must screen the family,
all three existing generated trees, and all 26 permanent Aider C++ holdouts.

This local audit does not require tokenizer/mask evidence or dataset splitting.
Public prompt bytes are 6,109–6,394 (median 6,256.5); private replacement bytes
are 5,433–6,354 (median 5,782). No model-tokenizer length conclusion is made.

## Independent Commands And Evidence

The audit independently recomputed the retained tree hash with the owner's
length-delimited path/content algorithm, enumerated every config and role,
rehashed every remedy target, and compared live owner/renderer/curriculum and
receipt files. It found:

- 80 roots, 80 IDs, 80 selected entries, 80 rejected cycle-001 entries, and 80
  cycle-002 remedy records;
- zero missing/extra role files, unsafe paths, role intersections, prompt
  private markers, symlinks, or hardlinks;
- one exact live tree hash across manifest, family screen, Docker receipt,
  mounted Docker tree, creator preflight, cycle record, and independent audit;
- Docker image
  `w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
  GCC 13.4.0 at `/usr/local/bin/c++` with compiler SHA-256
  `152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
  CMake 3.25.1, and `network_policy: none`;
- 731 legacy roots and 709 reverify roots matching their stored inventory
  hashes; and 1,665 live expansion roots whose current inventory hash does not
  match the stored source inventory (AEO-C02-F005).

Independent strict syntax checks compiled each reference and negative header
with `c++ -std=c++17 -Wall -Wextra -Wpedantic -Werror -fsyntax-only`, without
the owner's suppression. Only 29/80 references and 43/80 negatives compiled;
every failure was `-Werror=misleading-indentation` (AEO-C02-F002).

Independent UBSan probes used `-fsanitize=undefined
-fno-sanitize-recover=undefined` and `UBSAN_OPTIONS=halt_on_error=1`. Eight
task-specific boundary probes terminated on signed overflow/negation. Rebuilding
the emitted `temporal-floor-split` hidden test in the same halt-on-UB mode also
terminated at its `INT64_MIN` reconstruction expression (AEO-C02-F003).

## Findings

### AEO-C02-F001 — The hard-diversity screen admits forbidden clones

**Severity:** blocker

**Scope:** family screen, focused test, and at least five selected roots

The candidate evaluator uses overlap threshold 0.95, retains ordinary type,
field, parameter, and local identifiers, and substitutes only words from each
task ID. For controls it changes the threshold to 0.50 when
`common_lineage_task_id` is supplied. The controls therefore do not exercise
the same decision boundary used to admit candidate pairs.

Concrete selected pairs violate the binding hard rule:

- `temporal-floor-split` and `temporal-mjd-split` are the same Euclidean
  quotient/remainder algorithm and the same truncating-division negative with
  only domain names, units, constants, and result fields changed.
- `temporal-floor-split` and `temporal-nano-day` are the same split contract at
  another unit scale.
- `temporal-normalize-subsecond` and `temporal-normalize-nanos` are the same
  signed carry/borrow normalization with another modulus and field names.
- `temporal-nearest-era32` and `temporal-nearest-era10` teach the same nearest
  modular-era lift with a different bit width/modulus.
- `temporal-age-feb28` and `temporal-age-march1` are opposite-policy variants
  of the same completed-anniversary algorithm. Their recorded pair passes all
  seven dimensions even though the policy-only distinction is explicitly
  forbidden. Its reference-control-flow overlap is only 0.858156 because
  names such as `FebruaryObservedBirth` and `MarchObservedBirth` remain as
  diversity evidence.

The floor/MJD reference-control-flow overlap is reported as only 0.145299 even
though their control flow is structurally identical; local variable and field
names manufacture most of the difference. The focused test independently
tokenizes text but obtains every dimension's artifact scope from the production
`_dimension_text` helper, keeps identifiers, repeats the 0.95 threshold, and
calls the production helper for control dispositions. It therefore confirms
the same defect rather than detecting it.

**Disposition:** `replace` `temporal-mjd-split`, `temporal-nano-day`,
`temporal-normalize-nanos`, `temporal-nearest-era10`, and
`temporal-age-march1` with five genuinely different contracts. Keep the other
member of each listed lineage only after the corrected all-pairs screen passes.
The remaining 75 roots are `repair-and-reverify` pending a genuinely
identifier-insensitive 3,160-by-seven recomputation.

**Required verification:** one candidate threshold/policy and one independent
alpha/domain/literal-normalized evaluator; every pair passes every dimension;
all three coherent controls change files, pass their adjusted behavior in
normal and halt-on-UB sanitizer modes, and fail every dimension under the same
clone decision boundary.

### AEO-C02-F002 — The recorded build weakens the required strict warnings

**Severity:** blocker

**Scope:** all 80 receipts; 51 references and 37 negatives directly

The curriculum requires `-Wall -Wextra -Wpedantic -Werror` clean code. The
generated CMake adds `-Wno-misleading-indentation`. Removing that suppression
causes 51 references and 37 negatives to fail with exactly
`-Werror=misleading-indentation`. Therefore the Docker receipt proves a weaker
warning policy than the binding contract, and its `pass` cannot establish
strict-warning cleanliness.

Reference failures (51): `temporal-actuarial`, `temporal-affine-map`,
`temporal-age-band`, `temporal-age-borrowed`, `temporal-age-feb28`,
`temporal-age-fraction`, `temporal-age-march1`, `temporal-age-series`,
`temporal-arithmetic-sum`, `temporal-backoff`,
`temporal-birthday-nearest`, `temporal-bounded-add`,
`temporal-bucket-index`, `temporal-century-birthdays`,
`temporal-cohort-cutoff`, `temporal-common-timebase`,
`temporal-completed-months`, `temporal-compose-duration`,
`temporal-dot-product`, `temporal-drift-envelope`, `temporal-eligibility`,
`temporal-euclidean-div`, `temporal-euclidean-shard-key`,
`temporal-exact-ratio`, `temporal-gap-runs`, `temporal-gestational`,
`temporal-interpolate`, `temporal-interval-shift`, `temporal-iso-weeks`,
`temporal-join-nanos`, `temporal-leap-label`, `temporal-leapling-count`,
`temporal-majority-epoch`, `temporal-median-offset`, `temporal-milestone`,
`temporal-nth-occurrence`, `temporal-packet-order`, `temporal-quantize`,
`temporal-range-rescale`, `temporal-retirement`, `temporal-saturating-add`,
`temporal-serial-order`, `temporal-sibling-gap`,
`temporal-slew-distribution`, `temporal-step-lookup`,
`temporal-tolerance-dedup`, `temporal-unwrap16`, `temporal-utc-to-tai`,
`temporal-watermark`, `temporal-weighted-centroid`, and
`temporal-window-count`.

Negative failures (37): `temporal-actuarial`, `temporal-affine-map`,
`temporal-age-band`, `temporal-age-borrowed`, `temporal-age-clamped`,
`temporal-age-feb28`, `temporal-age-fraction`, `temporal-age-march1`,
`temporal-birthday-nearest`, `temporal-bounded-add`,
`temporal-bucket-index`, `temporal-common-timebase`,
`temporal-completed-months`, `temporal-day-product`,
`temporal-eligibility`, `temporal-euclidean-div`,
`temporal-euclidean-shard-key`, `temporal-exact-ratio`,
`temporal-gestational`, `temporal-interpolate`, `temporal-interval-shift`,
`temporal-iso-weeks`, `temporal-leapling-count`,
`temporal-majority-epoch`, `temporal-median-offset`,
`temporal-piecewise-offset`, `temporal-quantize`,
`temporal-range-rescale`, `temporal-rational-ticks`,
`temporal-retirement`, `temporal-serial-order`, `temporal-sibling-gap`,
`temporal-slew-distribution`, `temporal-step-lookup`,
`temporal-tai-to-utc`, `temporal-utc-to-tai`, and
`temporal-window-count`.

**Disposition:** repair the common renderer formatting and remove the warning
suppression; then `repair-and-reverify` every non-replaced root. A negative
must compile warning-clean before its failing test result counts.

### AEO-C02-F003 — Sanitizer evidence is fail-open and known UB passes it

**Severity:** blocker

**Scope:** all 80 sanitizer records; directly reproduced in nine roots/tests

The Docker verifier supplies `-fsanitize=address,undefined` but neither
`-fno-sanitize-recover=undefined` nor a halt-on-error `UBSAN_OPTIONS`. It accepts
the CTest process return code and does not scan a successful test's sanitizer
diagnostics. Recovering UBSan findings therefore remain return code zero.

This is not hypothetical. The emitted `temporal-floor-split` hidden test
reconstructs `INT64_MIN` as `day * 86400 + second_of_day`; the multiplication
itself is below `INT64_MIN`. The recorded sanitizer test passed, while an
independent halt-on-UB build terminated on that exact expression.

Independent boundary probes also terminated in these references:

- `temporal-affine-map`: negates `INT64_MIN` origin before checked addition;
- `temporal-interpolate`: negates `INT64_MIN` begin before checked addition;
- `temporal-quantize`: negates `INT64_MIN` while computing the error;
- `temporal-two-point-calibration`: negates an `INT64_MIN` first sample;
- `temporal-tai-to-utc`: negates an `INT64_MIN` table offset;
- `temporal-euclidean-shard-key`: negates an `INT64_MIN` anchor;
- `temporal-age-feb28`: overflows extreme-year subtraction; and
- `temporal-age-clamped`: overflows extreme-year subtraction.

Several hidden suites have only one substantive assertion, including
`temporal-delta2`, `temporal-gap-runs`, `temporal-packet-order`,
`temporal-reset-segments`, `temporal-tolerance-dedup`,
`temporal-transactional-sum`, `temporal-two-point-calibration`, and
`temporal-unwrap32`. This contradicts the metadata's uniform claim that every
hidden suite covers invalid input, a boundary, and a deterministic property,
and explains why valid counterexamples escaped.

**Disposition:** repair the named references/tests and the sanitizer runner;
invalidate sanitizer evidence for all 80 roots; then `repair-and-reverify`
every non-replaced root with fresh normal and fresh halt-on-UB ASan/UBSan
builds. Require no sanitizer diagnostic, not merely return code zero.

### AEO-C02-F004 — Four advertised core contracts remain absent or contradicted

**Severity:** blocker

**Scope:** `temporal-tolerance-dedup`, `temporal-packet-order`,
`temporal-delta2`, and `temporal-watermark`

- `temporal-tolerance-dedup` says connectivity compares adjacent inputs and
  explicitly forbids last-kept comparison. The reference compares each value
  to `out.back()`, and the visible oracle expects `{1,4,10}` for
  `{1,2,4,10}` at tolerance 2. The contract's connected-run result is
  `{1,10}`. The reference and oracle implement the named negative.
- `temporal-packet-order` says to order disjoint uncertainty intervals,
  preserve overlaps, reject negative uncertainty, and reject endpoint
  overflow. `PacketStamp` has no uncertainty field. The reference center-sorts
  timestamps—the named forbidden substitute—and checks duplicate sequence IDs
  only when adjacent in input.
- `temporal-delta2` says to reconstruct deltas and timestamps through two
  accumulators with transactional decoded output. Its API takes timestamps and
  its reference produces first value, first delta, and delta-of-delta values:
  it is an encoder, not the advertised decoder.
- `temporal-watermark` requires all active sources to be initialized and a
  missing active source to block advancement. `SourceTime` has no active or
  initialized state, so this behavior is unrepresentable.

These are deterministic contract/reference defects, not stylistic concerns;
passing the self-authored tests proves the substituted behavior instead.

**Disposition:** `repair-and-reverify` these four roots by implementing the
advertised APIs/mechanisms and adding independent discriminators for the exact
substitutes above. If the public objective cannot survive without becoming a
different contract, use `replace` and backfill the count.

### AEO-C02-F005 — Cross-tree and holdout semantic evidence is not bound or identifier-insensitive

**Severity:** blocker

**Scope:** family inventory, all 80 cross-tree/holdout dispositions

The stored source inventory says 1,665 expansion roots with hash
`d839b48a4e8f4375105d9e45678b0fdefffd170fc1da862f5065642fb0baed4c`.
The live inventory still has 1,665 roots but hashes to
`ed9f3665681d09a81749030d00d968c1a9895eb71037fc491149c6f5bc64b1ed`:
`mcn-angular-dms-normalizer` was removed and
`mcn-weighted-phase-histogram` was added. The family screen records only counts
and the strongest match, not the exact root list or inventory hash, so its
cross-tree claim cannot be reconciled to an immutable comparison subject.

The semantic screen also uses the same identifier-preserving tokenizer that
misses the within-family clones. It reports strongest overlap only 0.019882
across 3,025 existing/sibling roots and 0.001609 across the 26 holdouts. Those
near-zero values reflect unmatched clean-room identifiers and domains, not a
meaningful normalized API/control-flow/test comparison. Exact ID screening did
pass, and all 26 bound holdout roots are present, but those facts do not close
the required near-semantic screen.

**Disposition:** `repair-and-reverify` all non-replaced roots after freezing
all three exact sorted inventories and binding their hashes into the screen and
cycle. Recompute candidate/existing/holdout comparisons after removing ordinary
identifiers and domain nouns while preserving arity, operators, control flow,
invariants, and assertions. Any true overlap is `replace`/`reject`, never a
rename waiver.

## Duplicate, Revision, Lineage, And Contamination Report

- Exact selected IDs: 80 unique; no selected ID equals a cycle-001 ancestor,
  legacy, reverify, sibling expansion, or 26-holdout ID in the inspected
  manifests.
- Selected/rejected lineage: 80 one-to-one replacement relations; cycle-001
  ancestors remain only in rejected/remedy evidence and are absent from the
  selected tree.
- Exact public prompt/reference/hidden-test hashes within the selected family:
  80/80/80 unique. Exact unequal hashes do not rescue the semantic clones.
- Within-family semantic disposition: fail under the binding hard rule;
  AEO-C02-F001 identifies five selected roots that must be replaced.
- Cross-tree inventory: legacy and reverify snapshots are current; expansion
  snapshot is stale and the screen does not bind a root-list hash.
- Holdouts: all 26 local official C++ roots and all 26 denylist IDs are present.
  No prompt exposes a private candidate reference/test or an explicit holdout
  ID. Near-semantic contamination remains `not_completed` because the
  normalizer is not fit for the specified comparison.

## Corpus Composition

All 80 roots are repository-authored synthetic, deterministic, header-only,
single-turn C++17 whole-file tasks. Each has one editable header, two public
documentation files, one private reference, one private negative, visible and
hidden tests, private role/provenance/coverage metadata, and CMake. Groups are
balanced 20/20/20/20 across epoch/codecs, human age, checked arithmetic, and
rollover/order. The balanced labels do not establish behavioral diversity;
F001 finds constants/policy duplicates, and F004 finds missing advertised
mechanisms.

## Root-Level Audit Catalog

Finding abbreviations below mean AEO-C02-F001 through AEO-C02-F005. Every root
also inherits the family-level strict/sanitizer/inventory invalidation. A
`replace` root does not count toward 80 until a new backfill passes the full
loop; `repair-and-reverify` is not admission.

| Task ID | Group / operation | Cycle-001 ancestor | Direct findings | Disposition |
| --- | --- | --- | --- | --- |
| `temporal-floor-split` | epoch / `floor_split` | `unix-day-floor-split` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-normalize-subsecond` | epoch / `normalize_subsecond` | `unix-millisecond-normalizer` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-normalize-nanos` | epoch / `normalize_nanos` | `timespec-canonicalizer` | F001, F002, F003, F005 | `replace` |
| `temporal-fixed-fraction` | epoch / `fixed_fraction` | `ntp-fraction-decoder` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-nearest-era32` | epoch / `nearest_era32` | `ntp-era-unfolder` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-nearest-era10` | epoch / `nearest_era10` | `gps-week-era-resolver` | F001, F002, F003, F005 | `replace` |
| `temporal-week-seconds` | epoch / `week_seconds` | `gps-time-of-week-validator` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-filetime-split` | epoch / `filetime_split` | `filetime-tick-splitter` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-unsigned-epoch-offset` | epoch / `unsigned_epoch_offset` | `mac-epoch-offset-converter` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-mjd-split` | epoch / `mjd_split` | `modified-julian-day-split` | F001, F002, F003, F005 | `replace` |
| `temporal-excel-serial` | epoch / `excel_serial` | `excel-serial-compatibility` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-dos-fields` | epoch / `dos_fields` | `dos-packed-datetime` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-bcd-fields` | epoch / `bcd_fields` | `bcd-century-timestamp` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-signed48` | epoch / `signed48` | `signed-48bit-tick-decoder` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-step-lookup` | epoch / `step_lookup` | `tai-offset-table-lookup` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-utc-to-tai` | epoch / `utc_to_tai` | `utc-to-tai-checked` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-tai-to-utc` | epoch / `tai_to_utc` | `tai-to-utc-gap-aware` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-leap-label` | epoch / `leap_label` | `leap-second-label-validator` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-nano-day` | epoch / `nano_day` | `epoch-nanosecond-day-split` | F001, F002, F003, F005 | `replace` |
| `temporal-rational-ticks` | epoch / `rational_ticks` | `rational-clock-tick-converter` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-age-feb28` | age / `age_feb28` | `feb28-leapling-age` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-age-march1` | age / `age_march1` | `march1-leapling-age` | F001, F002, F003, F005 | `replace` |
| `temporal-age-clamped` | age / `age_clamped` | `clamped-calendar-age` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-age-borrowed` | age / `age_borrowed` | `borrowed-calendar-age` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-birthday-nearest` | age / `birthday_nearest` | `nearest-birthday-distance` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-milestone` | age / `milestone` | `next-milestone-birthday` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-majority-epoch` | age / `majority_epoch` | `majority-at-local-midnight` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-cohort-cutoff` | age / `cohort_cutoff` | `school-cohort-cutoff` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-actuarial` | age / `actuarial` | `actuarial-nearest-age` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-gestational` | age / `gestational` | `gestational-week-day-age` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-age-fraction` | age / `age_fraction` | `reduced-exact-age-fraction` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-age-band` | age / `age_band` | `age-band-locator` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-age-series` | age / `age_series` | `event-age-series` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-eligibility` | age / `eligibility` | `age-eligibility-window` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-leapling-count` | age / `leapling_count` | `leapling-birthday-counter` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-retirement` | age / `retirement` | `retirement-month-end-rule` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-sibling-gap` | age / `sibling_gap` | `sibling-age-gap-components` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-completed-months` | age / `completed_months` | `completed-month-age` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-iso-weeks` | age / `iso_weeks` | `completed-iso-week-age` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-century-birthdays` | age / `century_birthdays` | `century-birthday-enumerator` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-checked-add` | checked / `checked_add` | `checked-second-shift` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-compose-duration` | checked / `compose_duration` | `checked-duration-compose` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-exact-ratio` | checked / `exact_ratio` | `checked-unit-ratio-scale` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-saturating-add` | checked / `saturating_add` | `saturating-shift-report` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-bounded-add` | checked / `bounded_add` | `bounded-epoch-offset` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-day-product` | checked / `day_product` | `checked-day-second-product` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-join-nanos` | checked / `join_nanos` | `checked-second-nano-join` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-euclidean-div` | checked / `euclidean_div` | `euclidean-epoch-division` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-affine-map` | checked / `affine_map` | `checked-affine-clock-map` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-transactional-sum` | checked / `transactional_sum` | `transactional-duration-ledger` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-overflow-frontier` | checked / `overflow_frontier` | `overflow-prefix-frontier` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-interval-shift` | checked / `interval_shift` | `atomic-interval-shift` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-range-rescale` | checked / `range_rescale` | `checked-range-rescale` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-weighted-centroid` | checked / `weighted_centroid` | `weighted-timestamp-centroid` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-interpolate` | checked / `interpolate` | `checked-time-interpolation` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-nth-occurrence` | checked / `nth_occurrence` | `checked-recurrence-occurrence` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-backoff` | checked / `backoff` | `bounded-backoff-deadline` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-arithmetic-sum` | checked / `arithmetic_sum` | `checked-arithmetic-schedule-sum` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-dot-product` | checked / `dot_product` | `checked-duration-dot-product` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-window-count` | checked / `window_count` | `checked-window-count` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-unwrap32` | rollover / `unwrap32` | `unwrap-32bit-tick-stream` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-unwrap16` | rollover / `unwrap16` | `unwrap-16bit-bounded-step` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-serial-order` | rollover / `serial_order` | `rfc1982-serial-order` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-gps-sequence` | rollover / `gps_sequence` | `gps-week-sequence-unwrapper` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-reset-segments` | rollover / `reset_segments` | `epoch-reset-segmenter` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-two-point-calibration` | rollover / `two_point_calibration` | `two-point-clock-calibration` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-piecewise-offset` | rollover / `piecewise_offset` | `piecewise-clock-offset-map` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-median-offset` | rollover / `median_offset` | `median-clock-offset` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-drift-envelope` | rollover / `drift_envelope` | `drift-envelope-validator` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-packet-order` | rollover / `packet_order` | `stable-packet-time-order` | F002, F003, F004, F005 | `repair-and-reverify` |
| `temporal-watermark` | rollover / `watermark` | `source-watermark-advance` | F002, F003, F004, F005 | `repair-and-reverify` |
| `temporal-tolerance-dedup` | rollover / `tolerance_dedup` | `timestamp-tolerance-deduplicator` | F002, F003, F004, F005 | `repair-and-reverify` |
| `temporal-delta2` | rollover / `delta2` | `delta-of-delta-timestamp-codec` | F002, F003, F004, F005 | `repair-and-reverify` |
| `temporal-gap-runs` | rollover / `gap_runs` | `timestamp-gap-run-classifier` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-bucket-index` | rollover / `bucket_index` | `anchored-time-bucket-index` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-slew-distribution` | rollover / `slew_distribution` | `clock-slew-distributor` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-quantize` | rollover / `quantize` | `quantized-roundtrip-error` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-common-timebase` | rollover / `common_timebase` | `timebase-common-tick` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-tagged-era` | rollover / `tagged_era` | `multi-era-tagged-timestamp` | F002, F003, F005 | `repair-and-reverify` |
| `temporal-euclidean-shard-key` | rollover / `shard_key` | `temporal-shard-key` | F002, F003, F005 | `repair-and-reverify` |

## Cycle-001 Finding Closure

| Cycle-001 finding | Cycle-002 audit disposition |
| --- | --- |
| AEO-C01-F001 advertised mechanisms/APIs absent | Still open: four new roots contradict or cannot represent their advertised core mechanism (AEO-C02-F004). |
| AEO-C01-F002 four-template duplicate family | Still open: task-specific rendering exists, but at least five constants/policy clones are admitted by an identifier-sensitive screen (AEO-C02-F001). |
| AEO-C01-F003 incomplete/stale oracle evidence | Still open: warning suppression and fail-open UBSan invalidate the current receipt (AEO-C02-F002/F003). |
| AEO-C01-F004 holdout screen incomplete | Still open: all 26 holdouts are present, but the identifier-sensitive semantic result is not admissible (AEO-C02-F005). |
| AEO-C01-F005 expansion inventory incomplete/stale | Still open: the live expansion hash differs from the stored inventory and the screen does not bind an inventory hash (AEO-C02-F005). |

## Terminal Decision

Cycle 002 is not clean. The strongest truthful status is `not_completed`, with
0/80 verified retained roots, five `replace` dispositions, 75
`repair-and-reverify` dispositions, and five unresolved hard-gate findings.
The immutable cycle-001 report remains valid for its prior subject; this report
binds the exact cycle-002 subject above. Only a fresh independent audit of the
post-remediation, exact regenerated tree can record `local_family_verified`.
