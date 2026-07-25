# Epoch, Age, And Overflow Boundaries — Independent Audit Cycle 004

Audit date: 2026-07-22

Status: `not_completed`

Decision: **zero of 80 roots are retained as verified candidates**. All 80
roots have disposition `repair-and-reverify`. The exact cycle-004 tree passes
the recorded structural, diversity, live-inventory, holdout, and finite Docker
test gates, but the required coherent-control gate and full advertised integer
domain gate remain open.

## Confirmed Counts, Risks, And Next Gate

- Materialized roots: 80 unique selected IDs, balanced 20/20/20/20 across the
  four curriculum groups.
- Recorded Docker executions: 80 normal references, 80 nonrecovering
  ASan/UBSan references, 80 compiling rejected negatives, and three controls
  in both normal and sanitizer modes, with two discovered tests per execution.
- Recorded and independently recomputed diversity outcomes: all 3,160 pairs
  pass all seven required dimensions, for 22,120 passing dimension records.
  Candidate and control comparisons use the same 0.95 threshold after literal
  removal and ordinary-identifier alpha-normalization. Maximum selected-pair
  overlap is 0.421986 and minimum symmetric difference is 54.
- Live bound inventories: 731 legacy roots, 709 reverify roots, 1,585 sibling
  expansion roots, and 26 holdouts. Their independently recomputed hashes
  match the family screen.
- Focused tests: 6 passed in 17.07 seconds with the pytest cache disabled.
- Verified retained roots: 0. Two hard-gate findings remain open.
- Next gate: route AEO-C04-F001 and AEO-C04-F002 through
  `aider-task-family-remediation`; make the opposite-end control's public
  partition contract internally consistent; repair full-domain civil-date
  arithmetic for `temporal-age-clamped`; add the exact equal-date `INT64_MIN`
  probe; regenerate; rerun strict normal, nonrecovering sanitizer, negative,
  control, diversity, live-inventory, and holdout evidence; then submit the
  unchanged subject to independent audit cycle 005.

No SFT projection, dataset release, tokenizer/mask claim, split, training
authorization, or benchmark-uplift claim follows from this report.

## Frozen Audit Subject

- Family root:
  `.w8-biayn/data/aider-tasks-expansion-v1/aider-dates-and-clocks/epoch-age-overflow-boundaries/`
- Retained-task tree SHA-256, excluding `.state`:
  `fea3b7574970cbac0a8ac449ff280ebea5bcfabd917ca03d7efae1d05757ec14`
- Owner SHA-256:
  `af4b9591547b97f0e595a302d485fcf699572ad08cadbaaa15fa58e564697bdf`
- Task-specific renderer SHA-256:
  `02889514b796f79c0dca0f3ac8fd81357008c4d020b89c73dcf7d1d1d3061480`
- Curriculum SHA-256:
  `a4e316e9c78865e105405c98d61f2a12221ef699d01a75d71145f2a26d943b64`
- Focused-test SHA-256:
  `6d65c6442af71bb1db3cabb33aba0ea4506bfa8d4a72fa20eeb38a124264a02c`
- Family-screen SHA-256:
  `04a6bbaff897e6e1eb8047f6adbc9d8b1beb805908cc49e069deaba92fdbeb15`
- Docker-receipt SHA-256:
  `49c59df35600cf326825298e781c3a1a2e67714eecc0deee2a8a482325102edc`
- Creator-preflight SHA-256:
  `95f9b11acdfb0e78b1fcc973632b02c957249796886069eade4e3cb606dbb2e3`
- Cycle-004 record SHA-256:
  `faef38d44947a83a28ae63539349402f04fdb048a6907545697c7e1b8d23427b`
- Immutable cycle-003 report SHA-256:
  `2b1f767ecd936f2bbbb7d9773b7933a878cff54403e0657c86a085fb5dc1707a`
- Live legacy inventory: 731 roots, SHA-256
  `fcb3a9a3537f57584195652534cfdc490ebf5b69a60a6d24e37f61ecb94cafeb`.
- Live reverify inventory: 709 roots, SHA-256
  `d0eedeacf075e30b357100a92a5b39a524fba7a1290cf607a0d30aacd5202791`.
- Live sibling expansion inventory: 1,585 roots, SHA-256
  `557d27d7474647f649513a70ade985aa3de11caa9043ff1547ef674b61c329c4`.
- Live holdout inventory: 26 roots, SHA-256
  `04dad3196a16e174ca5d4d587dd225b9631b6d21d3d838dd4ad732ff36abc3c3`.
- Audit-subject SHA-256:
  `9cb4616e0658c7838ede52d45bd40aab64855826a128de8313a3891093b880f4`.

The audit-subject hash is SHA-256 of the exact UTF-8 lines
`tree_sha256=...`, `owner_sha256=...`, `renderer_sha256=...`,
`curriculum_sha256=...`, `focused_test_sha256=...`,
`family_screen_sha256=...`, `docker_receipt_sha256=...`,
`creator_preflight_sha256=...`, `cycle_004_sha256=...`,
`legacy_inventory_sha256=...`, `reverify_inventory_sha256=...`,
`live_sibling_inventory_sha256=...`, and `holdout_inventory_sha256=...`, in
that order, each terminated by one newline.

The cycle-004 record routes all four cycle-003 finding IDs and its 80 remedy
records bind the current selected roots pending fresh audit. The selected tree
has 80 unique IDs and the same exact role-separated 11-file task shape audited
in cycle 003. No implementation, task, state, receipt, or manifest byte was
changed by this audit.

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
after comments, strings, literals, ordinary identifiers, and clean-room domain
nouns are removed. The same threshold and feature policy must screen selected
pairs and coherent adversarial clones. The exact live legacy, reverify,
sibling expansion, and 26-holdout inventories must be bound to the decision.

This is a local-family audit. Tokenizer/mask evidence and dataset splitting are
not applicable, and no model-tokenizer length claim is made.

## Independent Commands And Evidence

The audit independently rehashed the frozen subject, recomputed all 3,160
pair decisions from the exact task artifacts, recomputed the four live
inventory records, inspected the three complete control trees, reviewed the
three cycle-003 contract repairs, and ran the focused tests. The recomputed
pair records exactly equal the recorded records; all 22,120 dimension records
pass at threshold 0.95.

The current Docker receipt binds the task tree and mounted tree to the same
SHA-256 and records image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
GCC 13.4.0 at `/usr/local/bin/c++` with compiler SHA-256
`152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
CMake 3.25.1, `--network none`,
`-fsanitize=address,undefined -fno-sanitize-recover=undefined`, and
halt-on-error ASan/UBSan options. This finite receipt does not cover inputs
absent from the emitted tests.

Three scoped closure probes were decisive:

1. `temporal_packet_order({{5,1},{3,1},{1,1}})` is now an explicit hidden
   counterexample and is rejected. The reference constructs checked interval
   precedence plus input-order overlap edges and uses a stable topological
   choice, returning `nullopt` when those constraints form a cycle. This closes
   the cycle-003 partial-order-as-sort-comparator defect for this subject.
2. A fresh nonrecovering UBSan probe of
   `temporal_exact_ratio(INT64_MIN,1,1)` exits zero and returns `INT64_MIN`.
   The exact emitted hidden test contains the same probe. This part of the
   cycle-003 overflow finding is closed.
3. A fresh strict nonrecovering UBSan probe of
   `temporal_age_clamped({INT64_MIN,1,1},{INT64_MIN,1,1})` terminates at
   `.meta/example.h:51` in `days_from_civil`, where `y -= 1` evaluates
   `INT64_MIN - 1`. The emitted hidden test does not contain this mandated
   probe. This is a deterministic counterexample to the advertised all-defined
   `int64_t` arithmetic contract.

## Findings

### AEO-C04-F001 — The opposite-end control's public contract is contradictory

**Severity:** blocker

**Scope:** family clone-control evidence

The changed reference and visible oracle now exercise an exact multiple:
input 86,400 returns day 0 and `second_of_day == 86400`. The changed output
range says `second_of_day` is in `[1,86401)`. However, the same public
instructions still require a split “using Euclidean division” and state that
“The remainder is always in [0, 86399].” The reference instead decrements the
quotient and represents an exact-zero remainder as 86,400. Those statements
cannot simultaneously describe the returned quotient/remainder pair.

The production evaluator correctly rejects this control in all seven
dimensions at the unchanged 0.95 threshold, and its finite normal and
sanitizer tests pass. That does not make the changed public task coherent. A
clone-control gate requires a behavior-passing *coherent* variant, not code and
a test attached to mutually inconsistent instructions.

**Disposition:** `repair-and-reverify` the family. Rewrite the complete public
partition policy consistently as either the standard Euclidean `[0,86400)`
representation or the preceding-day/right-closed `(0,86400]` representation,
then keep reference, visible and hidden exact-boundary tests, negative, and
normal/sanitizer control evidence aligned. Rerun the unchanged-threshold
seven-dimension clone rejection.

### AEO-C04-F002 — `temporal-age-clamped` still overflows at `INT64_MIN`

**Severity:** blocker

**Scope:** `temporal-age-clamped`

Cycle 004 removed the earlier `year * 12` path, but the equal-date minimum-year
case still reaches `detail::serial`, then `days_from_civil`. For January,
`days_from_civil` subtracts one from the year before era decomposition. At
`INT64_MIN` this is signed overflow. The independent nonrecovering UBSan probe
above terminates before returning the mathematically required zero age.

The cycle-004 hidden oracle covers leap-day clamping and invalid months but
omits the exact `INT64_MIN` probe required by AEO-C03-F004. Therefore the
passing Docker sanitizer record is current but insufficient: it proves only
the emitted finite cases, not the full advertised `int64_t` input domain.

**Disposition:** `repair-and-reverify` `temporal-age-clamped` using an
overflow-free civil-day difference or an equality/era decomposition that is
defined at both integer extremes. Add the exact equal-date `INT64_MIN` probe
to the private suite and regenerate fresh normal and nonrecovering ASan/UBSan
evidence.

## Cycle-003 Finding Closure

| Cycle-003 finding | Cycle-004 audit disposition |
| --- | --- |
| AEO-C03-F001 incoherent opposite control | Still open as AEO-C04-F001. The exact-zero behavior is now executed, but the public Euclidean/remainder statement contradicts the changed right-closed representation. |
| AEO-C03-F002 stale sibling inventory | Closed for this subject. The family screen and independent audit both bind 1,585 live sibling roots at SHA-256 `557d27...`; legacy, reverify, and holdout inventories also reconcile. |
| AEO-C03-F003 invalid packet partial-order comparator | Closed for this subject. The reference uses explicit precedence edges plus topological selection and rejects the three-interval cyclic counterexample in the hidden oracle. |
| AEO-C03-F004 two overflow-boundary references | Partially closed. `temporal-exact-ratio(INT64_MIN,1,1)` passes its emitted and independent nonrecovering sanitizer probe. `temporal-age-clamped` still terminates on the mandated equal-date minimum-year probe (AEO-C04-F002). |

## Duplicate, Revision, Lineage, And Contamination Report

- Selected IDs: 80 unique; no selected ID collision is reported against the
  live legacy, reverify, sibling, or 26-holdout inventories.
- Lineage: the cycle record contains 80 selected cycle-004 IDs and 80
  `repair-and-reverify` dispositions routed from the immutable cycle-003
  report. No rejected ancestor is presented beside its successor as an
  unrelated selected example.
- Within-family normalized screen: 3,160/3,160 pairs and all seven dimensions
  independently recompute as passing. Recorded and recomputed outcomes are
  byte-for-structure equal.
- Controls: all three classify as clones in all seven dimensions at the same
  0.95 threshold. `domain-identifier-renamed` and
  `constants-or-policy-only` are coherent; `opposite-end-selection` fails the
  coherent-public-contract gate (AEO-C04-F001).
- Cross-tree: exact-ID and normalized semantic screens pass against 731
  legacy, 709 reverify, and 1,585 sibling roots. Strongest recorded cross-tree
  overlap is 0.008276.
- Holdouts: all 26 local official C++ roots are bound. Strongest recorded
  normalized overlap is 0.001785 against `robot-name`; no benchmark
  contamination failure is reported.
- No existing task was overwritten or renamed into this family. The duplicate
  and contamination screens are clean for the frozen subject, but they do not
  override executable or coherent-control failures.

## Corpus Composition

All 80 roots are repository-authored synthetic, deterministic, header-only,
single-turn C++17 whole-file tasks. Each has one editable header, two public
documentation files, one private reference, one private negative, visible and
hidden tests, private config/provenance/test metadata, and CMake. Groups are
balanced 20 each across epoch/codecs, human age, checked arithmetic, and
rollover/order. Verification method is uniform Docker normal, ASan/UBSan, and
compiling-negative execution. The two blockers remain hard admission failures,
not soft diversity penalties.

## Root-Level Audit Catalog

AEO-C04-F001 is family-wide. AEO-C04-F002 marks the direct age-clamped defect.

| Task ID | Group | Direct note | Disposition |
| --- | --- | --- | --- |
| `temporal-floor-split` | epoch | F001 | `repair-and-reverify` |
| `temporal-normalize-subsecond` | epoch | F001 | `repair-and-reverify` |
| `temporal-epoch-range-intersection` | epoch | F001 | `repair-and-reverify` |
| `temporal-fixed-fraction` | epoch | F001 | `repair-and-reverify` |
| `temporal-nearest-era32` | epoch | F001 | `repair-and-reverify` |
| `temporal-era-consensus` | epoch | F001 | `repair-and-reverify` |
| `temporal-week-seconds` | epoch | F001 | `repair-and-reverify` |
| `temporal-filetime-split` | epoch | F001 | `repair-and-reverify` |
| `temporal-unsigned-epoch-offset` | epoch | F001 | `repair-and-reverify` |
| `temporal-leap-table-digest` | epoch | F001 | `repair-and-reverify` |
| `temporal-excel-serial` | epoch | F001 | `repair-and-reverify` |
| `temporal-dos-fields` | epoch | F001 | `repair-and-reverify` |
| `temporal-bcd-fields` | epoch | F001 | `repair-and-reverify` |
| `temporal-signed48` | epoch | F001 | `repair-and-reverify` |
| `temporal-step-lookup` | epoch | F001 | `repair-and-reverify` |
| `temporal-utc-to-tai` | epoch | F001 | `repair-and-reverify` |
| `temporal-tai-to-utc` | epoch | F001 | `repair-and-reverify` |
| `temporal-leap-label` | epoch | F001 | `repair-and-reverify` |
| `temporal-signed-duration-parts` | epoch | F001 | `repair-and-reverify` |
| `temporal-rational-ticks` | epoch | F001 | `repair-and-reverify` |
| `temporal-age-feb28` | age | F001 | `repair-and-reverify` |
| `temporal-age-threshold-date` | age | F001 | `repair-and-reverify` |
| `temporal-age-clamped` | age | F001, F002 | `repair-and-reverify` |
| `temporal-age-borrowed` | age | F001 | `repair-and-reverify` |
| `temporal-birthday-nearest` | age | F001 | `repair-and-reverify` |
| `temporal-milestone` | age | F001 | `repair-and-reverify` |
| `temporal-majority-epoch` | age | F001 | `repair-and-reverify` |
| `temporal-cohort-cutoff` | age | F001 | `repair-and-reverify` |
| `temporal-actuarial` | age | F001 | `repair-and-reverify` |
| `temporal-gestational` | age | F001 | `repair-and-reverify` |
| `temporal-age-fraction` | age | F001 | `repair-and-reverify` |
| `temporal-age-band` | age | F001 | `repair-and-reverify` |
| `temporal-age-series` | age | F001 | `repair-and-reverify` |
| `temporal-eligibility` | age | F001 | `repair-and-reverify` |
| `temporal-leapling-count` | age | F001 | `repair-and-reverify` |
| `temporal-retirement` | age | F001 | `repair-and-reverify` |
| `temporal-sibling-gap` | age | F001 | `repair-and-reverify` |
| `temporal-completed-months` | age | F001 | `repair-and-reverify` |
| `temporal-iso-weeks` | age | F001 | `repair-and-reverify` |
| `temporal-century-birthdays` | age | F001 | `repair-and-reverify` |
| `temporal-checked-add` | checked | F001 | `repair-and-reverify` |
| `temporal-compose-duration` | checked | F001 | `repair-and-reverify` |
| `temporal-exact-ratio` | checked | F001; C03 overflow probe closed | `repair-and-reverify` |
| `temporal-saturating-add` | checked | F001 | `repair-and-reverify` |
| `temporal-bounded-add` | checked | F001 | `repair-and-reverify` |
| `temporal-day-product` | checked | F001 | `repair-and-reverify` |
| `temporal-join-nanos` | checked | F001 | `repair-and-reverify` |
| `temporal-euclidean-div` | checked | F001 | `repair-and-reverify` |
| `temporal-affine-map` | checked | F001 | `repair-and-reverify` |
| `temporal-transactional-sum` | checked | F001 | `repair-and-reverify` |
| `temporal-overflow-frontier` | checked | F001 | `repair-and-reverify` |
| `temporal-interval-shift` | checked | F001 | `repair-and-reverify` |
| `temporal-range-rescale` | checked | F001 | `repair-and-reverify` |
| `temporal-weighted-centroid` | checked | F001 | `repair-and-reverify` |
| `temporal-interpolate` | checked | F001 | `repair-and-reverify` |
| `temporal-nth-occurrence` | checked | F001 | `repair-and-reverify` |
| `temporal-backoff` | checked | F001 | `repair-and-reverify` |
| `temporal-arithmetic-sum` | checked | F001 | `repair-and-reverify` |
| `temporal-dot-product` | checked | F001 | `repair-and-reverify` |
| `temporal-window-count` | checked | F001 | `repair-and-reverify` |
| `temporal-unwrap32` | rollover | F001 | `repair-and-reverify` |
| `temporal-unwrap16` | rollover | F001 | `repair-and-reverify` |
| `temporal-serial-order` | rollover | F001 | `repair-and-reverify` |
| `temporal-gps-sequence` | rollover | F001 | `repair-and-reverify` |
| `temporal-reset-segments` | rollover | F001 | `repair-and-reverify` |
| `temporal-two-point-calibration` | rollover | F001 | `repair-and-reverify` |
| `temporal-piecewise-offset` | rollover | F001 | `repair-and-reverify` |
| `temporal-median-offset` | rollover | F001 | `repair-and-reverify` |
| `temporal-drift-envelope` | rollover | F001 | `repair-and-reverify` |
| `temporal-packet-order` | rollover | F001; C03 counterexample closed | `repair-and-reverify` |
| `temporal-watermark` | rollover | F001 | `repair-and-reverify` |
| `temporal-tolerance-dedup` | rollover | F001 | `repair-and-reverify` |
| `temporal-delta2` | rollover | F001 | `repair-and-reverify` |
| `temporal-gap-runs` | rollover | F001 | `repair-and-reverify` |
| `temporal-bucket-index` | rollover | F001 | `repair-and-reverify` |
| `temporal-slew-distribution` | rollover | F001 | `repair-and-reverify` |
| `temporal-quantize` | rollover | F001 | `repair-and-reverify` |
| `temporal-common-timebase` | rollover | F001 | `repair-and-reverify` |
| `temporal-tagged-era` | rollover | F001 | `repair-and-reverify` |
| `temporal-euclidean-shard-key` | rollover | F001 | `repair-and-reverify` |

## Terminal Decision

Cycle 004 is not clean. The strongest truthful status is `not_completed`, with
0/80 verified retained roots, 80 `repair-and-reverify` dispositions, and two
unresolved hard-gate findings. The exact current diversity, live inventory,
holdout, packet-order, and exact-ratio evidence passes, but it cannot override
the incoherent required control or the reproduced signed-UB counterexample.
Only a fresh independent audit of the exact post-remediation regenerated tree
can record `local_family_verified`.
