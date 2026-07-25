# Epoch, Age, And Overflow Boundaries — Independent Audit Cycle 005

Audit date: 2026-07-22

Status: `not_completed`

Decision: **zero of 80 roots are retained as verified candidates**. All 80
roots have disposition `repair-and-reverify`. The exact cycle-005 tree passes
the recorded structural, diversity, live-inventory, holdout, strict Docker,
negative-discriminator, and focused-test gates. AEO-C04-F002 is closed, but
the required coherent-control gate remains open as AEO-C05-F001.

## Confirmed Counts, Risk, And Next Gate

- Materialized roots: 80 unique selected IDs, balanced 20/20/20/20 across the
  four curriculum groups.
- Recorded Docker executions: 80 normal references, 80 nonrecovering
  ASan/UBSan references, 80 compiling rejected negatives, and three controls
  in both normal and sanitizer modes, with two discovered tests per execution.
- Independently recomputed diversity outcomes: all 3,160 pairs pass all seven
  required dimensions, for 22,120 passing dimension records. The recomputed
  pair records exactly equal the recorded records. Maximum selected-pair
  overlap is 0.421986 and minimum symmetric difference is 54.
- Live bound inventories: 731 legacy roots, 709 reverify roots, 1,585 sibling
  expansion roots, and 26 holdouts. Independently recomputed counts, entries,
  and hashes match the family screen.
- Focused tests: 6 passed in 17.92 seconds with the pytest cache disabled.
- Verified retained roots: 0. One family-wide hard-gate finding remains open.
- Next gate: route AEO-C05-F001 through `aider-task-family-remediation`;
  remove or accurately qualify the false Euclidean-quotient claims in the
  opposite-end control while preserving the coherent right-closed
  `1..86400` representation; regenerate; rerun control normal/sanitizer and
  unchanged-threshold seven-dimension clone evidence; then submit the exact
  unchanged subject to independent audit cycle 006.

No SFT projection, dataset release, tokenizer/mask claim, split, training
authorization, or benchmark-uplift claim follows from this report.

## Frozen Audit Subject

- Family root:
  `.w8-biayn/data/aider-tasks-expansion-v1/aider-dates-and-clocks/epoch-age-overflow-boundaries/`
- Retained-task tree SHA-256, excluding `.state`:
  `dce6a0612c4daab9638e9168b5558403cc0041a984361e755583d373e67a638e`
- Owner SHA-256:
  `c7b35a7982694a470c10f93d79c2db051913bd914a03958f93e1605b0affa273`
- Task-specific renderer SHA-256:
  `e3b1ae5b784df425294550429c54b367867c7e55741cece9b89b9b6101bac107`
- Curriculum SHA-256:
  `e52b427cce37b4debd701586b4c6d42f40beafe31aec3b085145fa0ba93473f8`
- Focused-test SHA-256:
  `6d65c6442af71bb1db3cabb33aba0ea4506bfa8d4a72fa20eeb38a124264a02c`
- Family-screen SHA-256:
  `25608241b18c1628e0073c516e91cfe28dd80b945dd9def578c1d69a68ce412f`
- Docker-receipt SHA-256:
  `b51d616da1ac37aca55c8c0865503cbcbb12220845a8e4ed841a3514f44aab47`
- Creator-preflight SHA-256:
  `2d46e4cd3dc72d90a47c83ba81f358897402f6f79c232e048f0e285116f79368`
- Cycle-005 record SHA-256:
  `c655b577d9b33981a7f458fc7e0c1fccb405cfb6b63f0a76d84284b9bcfb4cf3`
- Immutable cycle-004 report SHA-256:
  `db367251ee22c0c2b5774d95e4463702cded4907c504b1c50738329585407185`
- Live legacy inventory: 731 roots, SHA-256
  `fcb3a9a3537f57584195652534cfdc490ebf5b69a60a6d24e37f61ecb94cafeb`.
- Live reverify inventory: 709 roots, SHA-256
  `d0eedeacf075e30b357100a92a5b39a524fba7a1290cf607a0d30aacd5202791`.
- Live sibling expansion inventory: 1,585 roots, SHA-256
  `557d27d7474647f649513a70ade985aa3de11caa9043ff1547ef674b61c329c4`.
- Live holdout inventory: 26 roots, SHA-256
  `04dad3196a16e174ca5d4d587dd225b9631b6d21d3d838dd4ad732ff36abc3c3`.
- Audit-subject SHA-256:
  `297ae3bf98c0f55cd1825f4fb7a18499c22cc9bef449b82db5433b899185da7f`.

The audit-subject hash is SHA-256 of the exact UTF-8 lines
`tree_sha256=...`, `owner_sha256=...`, `renderer_sha256=...`,
`curriculum_sha256=...`, `focused_test_sha256=...`,
`family_screen_sha256=...`, `docker_receipt_sha256=...`,
`creator_preflight_sha256=...`, `cycle_005_sha256=...`,
`legacy_inventory_sha256=...`, `reverify_inventory_sha256=...`,
`live_sibling_inventory_sha256=...`, and `holdout_inventory_sha256=...`, in
that order, each terminated by one newline.

The cycle-005 record routes both cycle-004 finding IDs; 80 cycle-005 remedy
records bind the current roots pending fresh audit. No implementation, task,
state, receipt, manifest, or prior audit byte was changed by this audit.

## Behavior Contract

The model must implement one exact C++17 whole-file header replacement from
the visible introduction, complete instructions, and starter only. Private
references, tests, negative fixtures, CMake, provenance, and receipts remain
outside the prompt. Every root must implement its named epoch, age,
large-range, or rollover mechanism with defined integer arithmetic over its
advertised input domain, documented invalid and boundary behavior,
deterministic tests, a compiling coherent wrong substitute that is rejected,
strict warnings, and clean normal plus fresh nonrecovering ASan/UBSan
execution.

Every retained pair must differ materially in all seven mandatory dimensions
after the declared normalization. The same 0.95 threshold and feature policy
must classify selected pairs and coherent adversarial clones. Each required
clone control must itself present a single coherent public behavior contract.
The exact live legacy, reverify, sibling expansion, and 26-holdout inventories
must be bound to the decision.

This is a local-family audit. Tokenizer/mask evidence and dataset splitting are
not applicable, and no model-tokenizer length claim is made.

## Independent Commands And Evidence

The audit independently rehashed the frozen subject, recomputed all 3,160 pair
decisions from the exact task artifacts, recomputed the four live inventory
records, inspected the cycle-005 control and age-clamped repairs, ran the
focused tests, and executed the exact `temporal-age-clamped` visible and hidden
oracles in a fresh pinned Docker sanitizer build. The fresh build used GCC
13.4.0, `-fsanitize=address,undefined`,
`-fno-sanitize-recover=undefined`, `ASAN_OPTIONS=detect_leaks=1:halt_on_error=1`,
and `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`; both tests passed.

The family Docker receipt binds retained and mounted tree hashes and records
image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
GCC 13.4.0 at `/usr/local/bin/c++` with compiler SHA-256
`152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
CMake 3.25.1, `--network none`, and nonrecovering sanitizer execution.

Two scoped closure probes were decisive:

1. `temporal_age_clamped({INT64_MIN,1,1},{INT64_MIN,1,1})` is present in the
   emitted hidden test. The reference checks exact date equality immediately
   after validation and returns `{0,0,0}` before `add_years_clamped`,
   `detail::serial`, or `days_from_civil`. The fresh nonrecovering sanitizer
   run passes both visible and hidden tests. AEO-C04-F002 is closed for this
   exact subject.
2. The opposite-end control's code and exact-zero visible test implement an
   algebraically valid right-closed partition: 86,400 returns day 0 and second
   86,400. Its public instructions nevertheless call that day value “the
   Euclidean day quotient.” The Euclidean quotient for 86,400 divided by
   86,400 is 1, so the public prose and executed return value still disagree.

## Finding

### AEO-C05-F001 — The right-closed control still falsely names its quotient Euclidean

**Severity:** blocker

**Scope:** family clone-control evidence

The cycle-005 control consistently changes the integer range to `[1,86400]`
and `[1,86401)`. Its reference shifts an exact-zero truncating remainder to
86,400 and decrements the quotient, and its visible exact-zero case verifies
`temporal_floor_split(86400) == {0,86400}`. Those bytes form a coherent
right-closed partition satisfying `input == day * 86400 + second_of_day`.

The same instructions still say both “using Euclidean division” and
“DaySecond.day is the Euclidean day quotient.” For the executed exact-multiple
case, Euclidean division produces quotient 1 and remainder 0; the control
returns quotient-like day 0 and remainder 86,400. The labels are therefore
mathematically false for the behavior the test requires. Passing normal and
sanitizer tests and rejection in all seven normalized clone dimensions do not
make a contradictory public contract coherent.

**Disposition:** `repair-and-reverify` the family. Describe the returned day as
the unique right-closed partition index, explicitly state the reconstruction
identity and `1 <= second_of_day <= 86400`, and remove or accurately qualify
the Euclidean quotient/remainder claims. Preserve the exact-zero case, then
rerun normal, nonrecovering sanitizer, and all-seven-dimension clone evidence.

## Cycle-004 Finding Closure

| Cycle-004 finding | Cycle-005 audit disposition |
| --- | --- |
| AEO-C04-F001 incoherent opposite control | Still open as AEO-C05-F001. Code, range, and exact-zero test now agree on a right-closed partition, but the public instructions falsely call the shifted day the Euclidean quotient. |
| AEO-C04-F002 `temporal-age-clamped` `INT64_MIN` overflow | Closed for this subject. The exact equal-date probe is emitted; the equality return occurs before civil conversion; fresh strict nonrecovering ASan/UBSan passes 2/2 tests. |

## Duplicate, Revision, Lineage, And Contamination Report

- Selected IDs: 80 unique; no selected ID collision exists against the live
  legacy, reverify, sibling, or 26-holdout inventories.
- Lineage: 80 cycle-005 remedy records route both cycle-004 findings and bind
  the selected roots. No rejected ancestor is presented beside its successor
  as an unrelated selected example.
- Within-family normalized screen: 3,160/3,160 pairs and all seven dimensions
  independently recompute as passing; recomputed and recorded pair structures
  match exactly.
- Controls: all three are rejected as clones in all seven dimensions at the
  same 0.95 threshold. The opposite-end control fails the independent coherent
  public-contract gate in AEO-C05-F001.
- Cross-tree: exact-ID and normalized semantic screens pass against 731
  legacy, 709 reverify, and 1,585 sibling roots. The recorded strongest
  cross-tree overlap is 0.008276.
- Holdouts: all 26 official local C++ roots are bound. The recorded strongest
  normalized overlap is 0.001785 against `robot-name`; no benchmark
  contamination failure is reported.
- No existing task was overwritten or renamed into this family. Clean
  duplicate and contamination results cannot override the required control's
  contradictory contract.

## Corpus Composition

All 80 roots are repository-authored synthetic, deterministic, header-only,
single-turn C++17 whole-file tasks. Each has one editable header, two public
documentation files, one private reference, one private negative, visible and
hidden tests, private config/provenance/test metadata, and CMake. Groups are
balanced 20 each across epoch/codecs, human age, checked arithmetic, and
rollover/order. Verification is uniform Docker normal, ASan/UBSan, and
compiling-negative execution. The remaining blocker is a hard family
admission failure, not a soft diversity penalty.

## Root-Level Audit Catalog

AEO-C05-F001 is family-wide, so every root remains pending one more regenerated
fresh audit. AEO-C04-F002 is closed for `temporal-age-clamped`.

| Task IDs | Group | Count | Direct note | Disposition |
| --- | --- | ---: | --- | --- |
| `temporal-floor-split`, `temporal-normalize-subsecond`, `temporal-epoch-range-intersection`, `temporal-fixed-fraction`, `temporal-nearest-era32`, `temporal-era-consensus`, `temporal-week-seconds`, `temporal-filetime-split`, `temporal-unsigned-epoch-offset`, `temporal-leap-table-digest`, `temporal-excel-serial`, `temporal-dos-fields`, `temporal-bcd-fields`, `temporal-signed48`, `temporal-step-lookup`, `temporal-utc-to-tai`, `temporal-tai-to-utc`, `temporal-leap-label`, `temporal-signed-duration-parts`, `temporal-rational-ticks` | epoch/codecs | 20 | F001 | `repair-and-reverify` |
| `temporal-age-feb28`, `temporal-age-threshold-date`, `temporal-age-clamped`, `temporal-age-borrowed`, `temporal-birthday-nearest`, `temporal-milestone`, `temporal-majority-epoch`, `temporal-cohort-cutoff`, `temporal-actuarial`, `temporal-gestational`, `temporal-age-fraction`, `temporal-age-band`, `temporal-age-series`, `temporal-eligibility`, `temporal-leapling-count`, `temporal-retirement`, `temporal-sibling-gap`, `temporal-completed-months`, `temporal-iso-weeks`, `temporal-century-birthdays` | human age | 20 | F001; age-clamped C04-F002 closed | `repair-and-reverify` |
| `temporal-checked-add`, `temporal-compose-duration`, `temporal-exact-ratio`, `temporal-saturating-add`, `temporal-bounded-add`, `temporal-day-product`, `temporal-join-nanos`, `temporal-euclidean-div`, `temporal-affine-map`, `temporal-transactional-sum`, `temporal-overflow-frontier`, `temporal-interval-shift`, `temporal-range-rescale`, `temporal-weighted-centroid`, `temporal-interpolate`, `temporal-nth-occurrence`, `temporal-backoff`, `temporal-arithmetic-sum`, `temporal-dot-product`, `temporal-window-count` | checked arithmetic | 20 | F001 | `repair-and-reverify` |
| `temporal-unwrap32`, `temporal-unwrap16`, `temporal-serial-order`, `temporal-gps-sequence`, `temporal-reset-segments`, `temporal-two-point-calibration`, `temporal-piecewise-offset`, `temporal-median-offset`, `temporal-drift-envelope`, `temporal-packet-order`, `temporal-watermark`, `temporal-tolerance-dedup`, `temporal-delta2`, `temporal-gap-runs`, `temporal-bucket-index`, `temporal-slew-distribution`, `temporal-quantize`, `temporal-common-timebase`, `temporal-tagged-era`, `temporal-euclidean-shard-key` | rollover/order | 20 | F001 | `repair-and-reverify` |

## Terminal Decision

Cycle 005 is not clean. The strongest truthful status is `not_completed`, with
0/80 verified retained roots, 80 `repair-and-reverify` dispositions, and one
unresolved family-wide hard-gate finding. AEO-C04-F002 and every current
structural, diversity, inventory, contamination, finite strict Docker,
negative-discriminator, and focused-test gate pass, but they cannot override
the incoherent required control. Only a fresh independent audit of the exact
post-remediation regenerated tree can record `local_family_verified`.
