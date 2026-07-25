# Epoch, Age, And Overflow Boundaries — Independent Audit Cycle 003

Audit date: 2026-07-22

Status: `not_completed`

Decision: **zero of 80 roots are retained as verified candidates**. All 80
roots have disposition `repair-and-reverify`. The exact task tree is
structurally valid, strict-warning clean, and accompanied by a current
tree-bound Docker receipt, but it does not pass the coherent adversarial-control,
live inventory, executable-contract, or overflow-boundary gates.

## Confirmed Counts, Risks, And Next Gate

- Materialized roots: 80 unique selected IDs, balanced 20/20/20/20 across the
  four curriculum groups.
- Structurally valid roots: 80. Every root has the exact 11-file shape, one
  editable header, one private reference, one private negative, two declared
  tests, disjoint roles, and a unique one-to-one replacement ancestor.
- Strict syntax: 160/160 current reference and negative headers compile with
  host GCC 13.3.0 under `-std=c++17 -Wall -Wextra -Wpedantic -Werror` with no
  warning suppression.
- Recorded Docker executions: 80 normal references, 80 nonrecovering
  ASan/UBSan references, 80 compiling rejected negatives, and three controls
  in both modes, with two discovered tests in every execution. This evidence
  is exact-tree bound, but the finite test suites miss the counterexamples in
  AEO-C03-F001, AEO-C03-F003, and AEO-C03-F004.
- Recorded family outcomes: all 3,160 pairs pass all seven dimensions, for
  22,120 passing dimension records. Candidates and controls use the same 0.95
  threshold after literal removal and alpha-normalization of ordinary
  identifiers. Maximum selected-pair overlap is 0.421986 and minimum selected
  symmetric difference is 54.
- Verified retained roots: 0. Four hard-gate findings remain open.
- Next gate: route AEO-C03-F001 through AEO-C03-F004 through
  `aider-task-family-remediation`; repair and behavior-test the third control,
  repair `temporal-packet-order`, `temporal-age-clamped`, and
  `temporal-exact-ratio`, freeze the then-live sibling inventory, regenerate,
  rerun strict Docker normal/nonrecovering-sanitizer/negative/control evidence,
  rerun the complete semantic screens, and submit the unchanged result to a
  fresh independent audit cycle 004.

No SFT projection, dataset release, tokenizer/mask claim, split, training
authorization, or benchmark-uplift claim follows from this report.

## Frozen Audit Subject

- Family root:
  `.w8-biayn/data/aider-tasks-expansion-v1/aider-dates-and-clocks/epoch-age-overflow-boundaries/`
- Retained-task tree SHA-256, excluding `.state`:
  `b5787d100c1d78ab0290c2146ea82677af9bd3172d1271cee7c2c468dd658984`
- Owner SHA-256:
  `e278986569125766e7b8048307418d0f799ba221c1456fc50a34e4d6e1f55f58`
- Task-specific renderer SHA-256:
  `77dc61df85ba4d0f2590299d194264a7ef4be60e396b03e22f757718d3368b09`
- Curriculum SHA-256:
  `984a703b0f33ebc44afdf48f7ae5ba0e442f995fb580ff8e39c0c3953ee1b9a5`
- Focused-test SHA-256:
  `6d65c6442af71bb1db3cabb33aba0ea4506bfa8d4a72fa20eeb38a124264a02c`
- Family-screen SHA-256:
  `822549dc5f3dc6de17d3ed1d718d167b936e07ac145dd2b99ce7becdac86c03b`
- Docker-receipt SHA-256:
  `ce5ad6a1a58c8d29a7f71e6a30bef14f45e15eae7da587a36e0cb51d3bb0dfa2`
- Creator-preflight SHA-256:
  `e53ff7e5430b2647ff70dc26400eff317b4a47f2095810783615c0fbbb02f949`
- Cycle-003 record SHA-256:
  `ea73666bbe426ec8b37c2b26fd077655c14c9e00b01020038d1a369a98c625f9`
- Live legacy inventory: 731 roots, SHA-256
  `fcb3a9a3537f57584195652534cfdc490ebf5b69a60a6d24e37f61ecb94cafeb`.
- Live reverify inventory: 709 roots, SHA-256
  `d0eedeacf075e30b357100a92a5b39a524fba7a1290cf607a0d30aacd5202791`.
- Live sibling expansion inventory at audit: 1,585 roots, SHA-256
  `df75a79a5a8e5d60e3bd614131d34c8839bb87de9b6a7a00d7085c87fee504a1`.
- Live holdout inventory: 26 roots, SHA-256
  `04dad3196a16e174ca5d4d587dd225b9631b6d21d3d838dd4ad732ff36abc3c3`.
- Audit-subject SHA-256:
  `06d6fdaa1bd350e93aa5b88dba53fda750de16862494d6bcaec8af489f42cd23`.

The audit-subject hash is SHA-256 of the exact UTF-8 lines
`tree_sha256=...`, `owner_sha256=...`, `renderer_sha256=...`,
`curriculum_sha256=...`, `focused_test_sha256=...`,
`family_screen_sha256=...`, `docker_receipt_sha256=...`,
`creator_preflight_sha256=...`, `cycle_003_sha256=...`,
`legacy_inventory_sha256=...`, `reverify_inventory_sha256=...`,
`live_sibling_inventory_sha256=...`, and `holdout_inventory_sha256=...`, in
that order, each terminated by one newline.

The selected tree has 80 unique public-prompt hashes, 80 unique reference
hashes, and 80 unique hidden-test hashes. It has no symlinks or multiply linked
files. All 80 cycle-003 remedy records reconcile their root, reference,
visible-test, hidden-test, and negative hashes to the live tree. The five
cycle-002 replacements are present under new IDs and the replaced selected IDs
are absent.

## Behavior Contract

The model must implement one exact C++17 whole-file header replacement from
the visible introduction, complete instructions, and starter only. Private
references, tests, negative fixtures, CMake, provenance, and receipts remain
outside the prompt. Every root must implement its named epoch, age,
large-range, or rollover mechanism with defined integer arithmetic, documented
invalid/boundary behavior, deterministic tests, a compiling coherent wrong
substitute that is rejected, strict warnings, and clean normal plus fresh
nonrecovering ASan/UBSan execution.

Every retained pair must differ materially in all seven mandatory dimensions
after comments, strings, literals, ordinary identifiers, and clean-room domain
nouns are removed. The same threshold and feature policy must screen selected
pairs and coherent adversarial clones. The exact live legacy, reverify, sibling
expansion, and 26-holdout inventories must be bound to the decision.

This is a local-family audit. Tokenizer/mask evidence and dataset splitting are
not applicable. Public prompt bytes are 6,110–6,396 (median 6,269.5); private
reference bytes are 5,436–6,377 (median 5,801.5). No model-tokenizer length
claim is made.

## Independent Commands And Evidence

The audit independently recomputed the length-delimited retained-tree hash,
enumerated every config and role, rehashed all cycle-003 remedies, compared
live owner/renderer/curriculum/test and receipt bytes, and found:

- 80 roots, 80 IDs, 80 selected entries, 80 cycle-003 remedies, and 80 unique
  replacement ancestors;
- zero missing/extra role files, unsafe role intersections, symlinks, hardlink
  groups, or duplicate prompt/reference/hidden-test hashes;
- exact tree/owner/renderer agreement across generator manifest, family screen,
  Docker receipt, mounted Docker tree, creator preflight, and cycle record;
- focused tests: 6 passed in 17.61 seconds with the pytest cache disabled;
- 3,160 selected pairs and 22,120 dimension records, all recorded passing at
  threshold 0.95; all three controls are recorded rejected in all seven
  dimensions at the same threshold;
- Docker image
  `w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
  GCC 13.4.0 at `/usr/local/bin/c++` with compiler SHA-256
  `152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
  CMake 3.25.1, `--network none`,
  `-fsanitize=address,undefined -fno-sanitize-recover=undefined`,
  `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1`, and
  `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`;
- no `-Wno-*` option in the owner, renderer, or 80 CMake files; and
- 731 live legacy roots, 709 live reverify roots, 1,585 live sibling roots,
  and all 26 holdouts.

The five required replacement IDs are materially new contracts rather than
renames of the five cycle-002 rejected roots:

| Replacement ID | Rejected cycle-002 root | Material mechanism |
| --- | --- | --- |
| `temporal-epoch-range-intersection` | `temporal-normalize-nanos` | validated closed-interval intersection |
| `temporal-era-consensus` | `temporal-nearest-era10` | agreement across every pivot's unique modular lift |
| `temporal-leap-table-digest` | `temporal-mjd-split` | ordered transition validation plus checked cumulative delta/span |
| `temporal-signed-duration-parts` | `temporal-nano-day` | unsigned magnitude decomposition with explicit sign and `INT64_MIN` handling |
| `temporal-age-threshold-date` | `temporal-age-march1` | checked nonnegative-age threshold date with month-end clamp |

Their 385 pair records against the other selected roots all pass every
dimension; the strongest per-dimension overlap among those records is 0.322767.

The audit also executed three answer-blind counterexamples:

1. The `opposite-end-selection` control's exact diff changes only
   `.meta/example.h` from `second < 0` to `second < 1`. Input zero is not in
   either test, so its recorded success does not validate the changed policy.
2. `temporal_packet_order({{5,1},{3,1},{1,1}})` returns indices `{0,1,2}`.
   Its uncertainty intervals are `[4,6]`, `[2,4]`, and `[0,2]`, so the first
   and third are provably disjoint but remain in reverse temporal order.
3. Fresh `-fsanitize=undefined -fno-sanitize-recover=undefined` probes with
   halt-on-error terminate for
   `temporal_age_clamped({INT64_MIN,1,1},{INT64_MIN,1,1})` at signed
   `INT64_MIN * 12`, and for
   `temporal_exact_ratio(INT64_MIN,1,1)` in `std::gcd` while negating
   `INT64_MIN`.

## Findings

### AEO-C03-F001 — The third adversarial control is not coherent

**Severity:** blocker

**Scope:** family clone-control evidence

`domain-identifier-renamed` changes only presentation and correctly retains
the source behavior. `constants-or-policy-only` changes its reference, tests,
negative, and instructions consistently and passes adjusted normal and
sanitizer executions. In contrast, `opposite-end-selection` changes only the
reference predicate `second < 0` to `second < 1`. Its instructions still
require Euclidean remainder `[0,86399]`, its visible and hidden tests are
byte-identical to the source tests, and neither test supplies a multiple of
86,400. For input zero the changed reference returns day `-1`, second 86,400,
contradicting the unchanged contract.

The semantic evaluator correctly calls this a clone in all dimensions at the
same 0.95 threshold, but the required control must also be coherent and pass
tests adjusted to its changed behavior. A passing non-discriminating test is
not positive control evidence.

**Disposition:** `repair-and-reverify` the family. Replace this control with a
genuine coherent opposite-end policy variant, change its public contract,
reference, and both relevant tests consistently, prove the changed case is
executed in normal and nonrecovering sanitizer modes, and require rejection in
all seven dimensions under the unchanged candidate threshold.

### AEO-C03-F002 — The bound sibling inventory is stale

**Severity:** blocker

**Scope:** cross-tree duplicate and contamination evidence for all 80 roots

The family screen freezes 1,570 sibling expansion roots with SHA-256
`3c2942d60f09f4f648f00438d114dad833ff97bda0c5d9c682989468b35d34e6`.
The live audit inventory has 1,585 roots with SHA-256
`df75a79a5a8e5d60e3bd614131d34c8839bb87de9b6a7a00d7085c87fee504a1`.
Fifteen `validation-parsing/lexical-canonicalization-eoi` roots were added and
none was removed. The screen therefore never compared the candidate family to
the exact live sibling subject.

Legacy (731), reverify (709), and holdout (26) inventory hashes reconcile.
Exact selected IDs do not collide with the live inventories, but absence of an
exact ID collision does not substitute for the required normalized semantic
screen.

**Disposition:** `repair-and-reverify` all 80 roots after sibling writes have
settled. Bind the exact sorted live inventory and rerun the identifier/literal
normalized semantic comparison. Any discovered contract clone is `replace` or
`reject`, not a rename waiver.

### AEO-C03-F003 — `temporal-packet-order` still violates its advertised contract

**Severity:** blocker

**Scope:** `temporal-packet-order`

The replacement API now represents uncertainty and rejects negative values and
endpoint overflow, closing part of AEO-C02-F004. Its sorter nevertheless uses
`std::stable_sort` with comparator `hi[a] < lo[b]`. Interval non-overlap is a
strict partial order, not a strict weak ordering: overlap incomparability is
not transitive, so it is not a legal sorting comparator.

The executed three-interval counterexample above returns `{0,1,2}` and leaves
two provably disjoint intervals in reverse order. The current visible case and
hidden two-interval overlap case do not exercise a chained-overlap ordering
conflict. Thus the reference and oracle do not implement the stated core
mechanism even though the named center-sort negative is rejected.

**Disposition:** `repair-and-reverify` this root with a coherent, explicitly
specified ordering rule and an algorithm that does not pass a partial order to
`stable_sort`. Add the three-interval counterexample and a property check that
every ordered disjoint pair respects the contract. If preserving every
overlapping input pair makes the objective cyclic, revise or replace the
contract rather than weakening the test.

### AEO-C03-F004 — Two overflow-boundary references still execute signed UB

**Severity:** blocker

**Scope:** `temporal-age-clamped` and `temporal-exact-ratio`

The nonrecovering sanitizer runner itself is repaired, and the eight probes
listed by cycle 002 no longer use the earlier unchecked negations/subtractions.
However, the required boundary behavior is still absent in two references:

- `temporal-age-clamped` accepts valid `int64_t` years. Equal birth/as-of dates
  at year `INT64_MIN` reach `add_months_clamped`, which evaluates
  `year * 12` and terminates under UBSan.
- `temporal-exact-ratio(INT64_MIN,1,1)` is mathematically integral and
  representable, but passes `INT64_MIN` to signed `std::gcd`; libstdc++ negates
  it and UBSan terminates.

Neither current hidden suite exercises these values. The Docker receipt proves
only the emitted cases, not the public all-defined-arithmetic contract.

**Disposition:** `repair-and-reverify` both roots using unsigned-magnitude or
checked decompositions that cover the full advertised input domain. Add these
exact probes to private tests and regenerate fresh normal plus nonrecovering
ASan/UBSan evidence.

## Cycle-002 Finding Closure

| Cycle-002 finding | Cycle-003 audit disposition |
| --- | --- |
| AEO-C02-F001 hard-diversity screen admits clones | Partially closed: the five required roots are materially replaced, ordinary identifiers/literals are normalized, 3,160×7 selected outcomes pass, and controls use the same 0.95 threshold. Still open because one required control is behaviorally incoherent (AEO-C03-F001). |
| AEO-C02-F002 strict warnings weakened | Closed for this subject: no suppression remains, all 80 CMake files specify the four strict flags, Docker builds pass, and 160/160 reference/negative headers independently pass strict host syntax. |
| AEO-C02-F003 fail-open sanitizer and reproduced UB | Partially closed: UBSan is nonrecovering and halt-on-error is set. The old floor-split reconstruction is removed and the named unchecked negations/subtractions are repaired, but two valid boundary probes still terminate (AEO-C03-F004). |
| AEO-C02-F004 four core contracts contradicted | Partially closed: watermark state, adjacent-input tolerance deduplication, and two-accumulator delta decoding are now represented and discriminated. Packet ordering still fails its contract (AEO-C03-F003). |
| AEO-C02-F005 inventories unbound / identifier-sensitive | Partially closed: exact inventory entries/hashes and identifier/literal normalization are now recorded, and legacy/reverify/holdout inventories reconcile. The sibling hash is stale against the audit-time tree (AEO-C03-F002). |

## Duplicate, Revision, Lineage, And Contamination Report

- Selected IDs: 80 unique; no selected ID equals a cycle-002 replaced ID, a
  legacy/reverify root, a sibling root, or a 26-holdout ID at audit time.
- Lineage: 80 explicit unique ancestors and 80 hash-aligned cycle-003 remedy
  records. Replaced roots are not materialized beside their successors as
  unrelated selected examples.
- Exact selected prompt/reference/hidden-test hashes: 80/80/80 unique.
- Within-family normalized screen: 3,160/3,160 pairs and all seven dimensions
  recorded pass. The five new replacements are materially distinct.
- Controls: all three are classified as clones in all dimensions at the same
  threshold, but one lacks a coherent executable changed contract (F001).
- Cross-tree: exact-ID screening passes. Legacy and reverify inventories are
  current; sibling semantic evidence is stale (F002).
- Holdouts: all 26 local official C++ roots and denylist IDs are present and
  bound. The recorded strongest normalized overlap is 0.001785 against
  `robot-name`; no prompt exposes an explicit holdout ID or private candidate
  reference/test.
- No existing task was overwritten or renamed into this family. Because the
  live sibling normalized comparison has not run, the stronger no-semantic-
  duplicate claim remains `not_completed`.

## Corpus Composition

All 80 roots are repository-authored synthetic, deterministic, header-only,
single-turn C++17 whole-file tasks. Each has one editable header, two public
documentation files, one private reference, one private negative, visible and
hidden tests, private config/provenance/test metadata, and CMake. Groups are
balanced 20 each across epoch/codecs, human age, checked arithmetic, and
rollover/order. Verification method is uniform Docker normal,
ASan/UBSan, and compiling-negative execution. The four blockers prevent local
family admission; they are not converted into soft diversity penalties.

## Root-Level Audit Catalog

`F001/F002` are family-wide. `F003/F004` mark direct task defects. A cycle-002
replacement note means the new contract itself is materially new; it does not
waive the family-wide gates.

| Task ID | Group | Direct note | Disposition |
| --- | --- | --- | --- |
| `temporal-floor-split` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-normalize-subsecond` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-epoch-range-intersection` | epoch | F001, F002; material cycle-002 replacement | `repair-and-reverify` |
| `temporal-fixed-fraction` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-nearest-era32` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-era-consensus` | epoch | F001, F002; material cycle-002 replacement | `repair-and-reverify` |
| `temporal-week-seconds` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-filetime-split` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-unsigned-epoch-offset` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-leap-table-digest` | epoch | F001, F002; material cycle-002 replacement | `repair-and-reverify` |
| `temporal-excel-serial` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-dos-fields` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-bcd-fields` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-signed48` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-step-lookup` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-utc-to-tai` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-tai-to-utc` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-leap-label` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-signed-duration-parts` | epoch | F001, F002; material cycle-002 replacement | `repair-and-reverify` |
| `temporal-rational-ticks` | epoch | F001, F002 | `repair-and-reverify` |
| `temporal-age-feb28` | age | F001, F002 | `repair-and-reverify` |
| `temporal-age-threshold-date` | age | F001, F002; material cycle-002 replacement | `repair-and-reverify` |
| `temporal-age-clamped` | age | F001, F002, F004 | `repair-and-reverify` |
| `temporal-age-borrowed` | age | F001, F002 | `repair-and-reverify` |
| `temporal-birthday-nearest` | age | F001, F002 | `repair-and-reverify` |
| `temporal-milestone` | age | F001, F002 | `repair-and-reverify` |
| `temporal-majority-epoch` | age | F001, F002 | `repair-and-reverify` |
| `temporal-cohort-cutoff` | age | F001, F002 | `repair-and-reverify` |
| `temporal-actuarial` | age | F001, F002 | `repair-and-reverify` |
| `temporal-gestational` | age | F001, F002 | `repair-and-reverify` |
| `temporal-age-fraction` | age | F001, F002 | `repair-and-reverify` |
| `temporal-age-band` | age | F001, F002 | `repair-and-reverify` |
| `temporal-age-series` | age | F001, F002 | `repair-and-reverify` |
| `temporal-eligibility` | age | F001, F002 | `repair-and-reverify` |
| `temporal-leapling-count` | age | F001, F002 | `repair-and-reverify` |
| `temporal-retirement` | age | F001, F002 | `repair-and-reverify` |
| `temporal-sibling-gap` | age | F001, F002 | `repair-and-reverify` |
| `temporal-completed-months` | age | F001, F002 | `repair-and-reverify` |
| `temporal-iso-weeks` | age | F001, F002 | `repair-and-reverify` |
| `temporal-century-birthdays` | age | F001, F002 | `repair-and-reverify` |
| `temporal-checked-add` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-compose-duration` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-exact-ratio` | checked | F001, F002, F004 | `repair-and-reverify` |
| `temporal-saturating-add` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-bounded-add` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-day-product` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-join-nanos` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-euclidean-div` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-affine-map` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-transactional-sum` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-overflow-frontier` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-interval-shift` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-range-rescale` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-weighted-centroid` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-interpolate` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-nth-occurrence` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-backoff` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-arithmetic-sum` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-dot-product` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-window-count` | checked | F001, F002 | `repair-and-reverify` |
| `temporal-unwrap32` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-unwrap16` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-serial-order` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-gps-sequence` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-reset-segments` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-two-point-calibration` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-piecewise-offset` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-median-offset` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-drift-envelope` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-packet-order` | rollover | F001, F002, F003 | `repair-and-reverify` |
| `temporal-watermark` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-tolerance-dedup` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-delta2` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-gap-runs` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-bucket-index` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-slew-distribution` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-quantize` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-common-timebase` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-tagged-era` | rollover | F001, F002 | `repair-and-reverify` |
| `temporal-euclidean-shard-key` | rollover | F001, F002 | `repair-and-reverify` |

## Terminal Decision

Cycle 003 is not clean. The strongest truthful status is `not_completed`, with
0/80 verified retained roots, 80 `repair-and-reverify` dispositions, and four
unresolved hard-gate findings. The immutable cycle-001 and cycle-002 reports
remain valid for their prior subjects; this report binds the exact cycle-003
task subject and the audit-time live inventories above. Only a fresh
independent audit of the exact post-remediation regenerated tree can record
`local_family_verified`.
