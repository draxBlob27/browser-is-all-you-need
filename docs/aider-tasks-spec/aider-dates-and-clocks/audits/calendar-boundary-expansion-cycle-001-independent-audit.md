# Calendar Boundary Expansion: Cycle 001 Independent Audit

## Result

Decision: **repair-and-reverify**. This exact subject does not pass independent
audit and must not be labeled `local_family_verified`.

- Audit subject: `sha256:4c5e10b37d0ea18bb9db57548bfa43a428c7ac459562d52d43d7db0ec2e995e0`
- Recomputed subject hash: exact match
- Recomputed generated-tree hash:
  `sha256:6a2cf51cebb6379835d59222ece3b28db6fa3520cc9d115ca41fe0c5eb42bc82`
- Creator-selected roots: 90
- Roots satisfying all applicable hard gates after this audit: **0**
- Controls (not roots): 3
- Stable findings: 7 open, including 3 critical and 4 high
- Dataset release, tokenization, split, SFT, training, and uplift: not requested
  and not assessed

The structure, prompt-role boundary, provenance presence, and recorded Docker
executions reconcile. They do not overcome deterministic reference/contract
counterexamples, semantic duplicates, incomplete behavioral assertions, or
incomplete audit-subject bindings.

## Behavior contract used by this audit

| Field | Audited requirement |
| --- | --- |
| Task | Create clean-room C++17 Aider roots for calendar differences, increments, leap rules, and month-end boundaries. |
| Inputs | Prompt-visible `.docs` and exactly two task-ID-named starter files; private references, tests, controls, and receipts remain hidden. |
| Output | A complete whole-file C++17 implementation of the task-specific metric, transform, or series API. |
| Invariants | Valid proleptic Gregorian years 1..9999; explicit boundary and invalid behavior; no undefined overflow; ordered, duplicate-free series; no semantic duplicates or holdout leakage. |
| Failure behavior | Invalid inputs, reversed spans, invalid parameters, and out-of-range results follow the public optional-return contract. |
| Resource limits | Offline CMake/GCC build in the pinned image, strict warnings, network disabled, normal plus fresh ASan/UBSan. |
| Evaluation | Visible and hidden deterministic behavioral checks, coherent wrong-substitute rejection, seven-dimension family screen, existing-tree lineage screen, and exact 26-root holdout screen. |
| Generalization | Distinct civil-calendar mechanisms rather than renamed, constants-only, opposite-end, or otherwise equivalent tasks. |

## Evidence inventory and gate counts

| Gate | Raw count/result | Audit disposition |
| --- | ---: | --- |
| Generated task roots/configs/references/hidden tests/wrong substitutes | 90/90/90/90/90 | Structural pass |
| Selected manifest | 90 requested, 90 retained, 90 unique IDs | Count reconciles; selection not admitted |
| Provenance | 90 `new-root`, one family, Apache-2.0, generator-owned | Presence pass; immutable source inventory fails CAL-C01-005 |
| Prompt records | 90 records, 90 unique hashes | Role-boundary pass; all reconstructed prompts lacked private-role names |
| Pair matrix | 4,005 pairs x 7 recorded dimensions | Fail: deterministic duplicates pass the screen (CAL-C01-001) |
| Clone controls | 3 controls, 6 Docker mode records | Executed and rejected by the current screen; screen is not semantically sound |
| Existing-tree screen | 129,600 comparisons (90 x 1,440) | Inconclusive under CAL-C01-006 |
| Holdout screen | 2,340 comparisons (90 x 26) | No direct match reported; evidence is incomplete under CAL-C01-006 |
| Docker task records | 180 (90 normal + 90 sanitizer) | Execution count pass; behavioral sufficiency fails CAL-C01-004 |
| Docker control records | 6 (3 normal + 3 sanitizer) | Execution count pass |
| Positive discovery | 2 tests in each of 186 mode records | Count pass; assertions insufficient |
| Wrong-substitute execution | Nonzero in each of 186 mode records | Mechanical rejection pass; discriminator coverage insufficient |
| All-hard-gate root count | 0 | Requested retained-pass bound is not met in cycle 001 |

The Docker receipt identifies the pinned image digest, GCC 13.4.0, CMake
3.25.1, and `--network none`. Its `locked_oracle` field is `false`, and it does
not record the compiler path or binary digest.

## Findings

### CAL-C01-001 — critical — semantic duplicates pass the family screen

The family contains at least four exact observable-equivalence groups:

1. `calendar-signed-day-distance` and `calendar-absolute-day-gap`. Both reject
   a reversed range before their core runs, so `abs(serial(last)-serial(first))`
   is exactly `serial(last)-serial(first)` on the entire accepted domain.
2. `calendar-crossed-month-boundaries` and
   `calendar-endpoint-month-index-delta`. Counting month transitions on an
   ordered interval is exactly the linear month-coordinate difference.
3. `leapseries-month-end-partition`, `leapseries-eom-monthly-anchor`, and
   `leapseries-month-capacity-vector`. All three emit the same in-span month
   terminals; only the loop spelling and task words differ.
4. `leapseries-month-fragment-lengths` and
   `leapseries-monthly-proration-vector`. The two reference loops produce the
   same per-month fragment-length encoding.

This accounts for five non-canonical duplicate roots. The recorded pair rows
nonetheless say `pass: true`. For example, the fragment/proration pair reports
all dimensions distinct even though its two cores differ only by storing the
same `min(...)` value in a temporary. The evaluator reduces artifacts to token
sets, normalizes every literal to `NUMBER`, ignores token order, and accepts a
dimension with any one-token symmetric difference below 0.97.

Evidence:

- generator lines 300-305, 326, 368-395;
- ordered-range validation at generator line 430;
- token-set normalizer/evaluator at generator lines 849-915;
- `.state/family-screen.json`, specifically the four pair records above;
- focused test lines 90-113, which asserts the evaluator's output rather than
  observable non-equivalence.

Disposition: retain no duplicate unchanged. Preserve one canonical objective
per equivalence group and replace or substantively redesign the other five;
then regenerate all 4,005 comparisons with an evaluator that detects
observable/API/test equivalence. Family gate: fail.

### CAL-C01-002 — critical — series references violate their public value contract

The common contract says every series is a chronological, duplicate-free
`vector<Date>`. Four references encode integer lengths/gaps by calling
`civil(length)` and therefore return synthetic year-1-or-later dates rather
than calendar boundaries. The resulting vectors can be unsorted and contain
duplicates:

- `leapseries-month-fragment-lengths`;
- `leapseries-leap-status-run-lengths`;
- `leapseries-monthly-proration-vector`;
- `leapseries-leap-gap-vector`.

For `[2023-12-15, 2024-05-20]`, month-fragment/proration produce encoded values
equivalent to `0001-01-17, 0001-01-31, 0001-01-29, 0001-01-31, ...`: not
chronological and not unique. This directly contradicts the prompt and family
specification; Docker passes because the hidden test compares only one modular
digest generated from the same representation.

Evidence:

- family specification lines 38-48 and 166-174;
- curriculum lines 32-47;
- generator series cores at lines 381-382 and 394-395;
- each named root's `.docs/instructions.md` and `.meta/example.cpp`;
- generator digest-only assertion at lines 477-490.

Disposition: repair the public representation and contract, or replace these
roots with genuinely date-valued series. Add element-wise property assertions
for order, uniqueness, representation, and exact semantic values. Root gate:
fail for all four.

### CAL-C01-003 — critical — range-edge references are wrong or nonterminating

Raw reference inspection yields concrete boundary failures:

- `leapseries-capacity-run-starts` omits the first in-range run. For
  `[2023-12-15, 2024-05-20]`, it starts at `2024-02-01` instead of representing
  the in-range December/January capacity run promised by its prompt.
- `leapseries-capacity-change-pairs` may emit a terminal after `last`; the same
  range emits `2024-05-31` although `last` is May 20.
- `monthend-next-boundary` returns an invalid zero date for input
  `9999-12-31` instead of `nullopt`.
- Month-step loops can become nonterminating after stepping past December
  9999 because `add_months_clamped` returns `{}`, while `serial({})` remains
  below the upper endpoint. Affected raw cores include
  `calendar-month-fragment-count`, `leapseries-clamped-monthly-anchor`,
  `leapseries-eom-monthly-anchor`, `leapseries-rolled-monthly-anchor`,
  `leapseries-month-capacity-vector`, `leapseries-month-end-offsets`,
  `leapseries-month-start-offsets`, `leapseries-capacity-run-starts`, and
  `leapseries-capacity-change-pairs`.

Evidence:

- support and month-step implementation at generator lines 250-299;
- transform core at line 343;
- metric core at line 314;
- series cores at lines 375-396;
- the `leapseries-capacity-run-starts` prompt's explicit “including the first
  in-range run” requirement;
- absence of year-9999 tests in generated visible/hidden test sources.

Disposition: repair all affected owner cores and Python oracle logic, add
timeout-bounded lower/upper-domain tests, regenerate, and rerun normal plus
fresh sanitizer verification. Root gate: fail for the listed roots.

### CAL-C01-004 — high — the executable oracle does not assert the material contract

Every root has only one public result example, one private result example, and
one invalid-date check. There are no executed per-root properties for the
contract's reversed intervals, parameter domains, empty results, endpoint
inclusion, equality/ties, order, duplicates, lower/upper year limits,
round-trip support invariant, or overflow/termination. Series correctness is
reduced to one modular digest. Transform private tests use only `2000-02-29`
and do not cross both 1900 and 2000, contrary to the curriculum/spec claim.

The wrong-substitute selector only searches for another operation whose two
fixed example outputs differ. Thus a nonzero wrong-substitute exit proves only
those examples differ; it does not establish a task-specific invariant. The
known defects in CAL-C01-002 and CAL-C01-003 pass all 180 task-mode records.

Evidence:

- test generator at lines 454-491;
- wrong-substitute selection at lines 742-756;
- Docker execution at lines 999-1055;
- curriculum lines 49-63;
- family specification lines 150-174;
- all 90 `task_visible_test.cpp` and `.meta/task_hidden_test.cpp` files.

Disposition: `repair-and-reverify` for all 90 roots. Define the full parameter
and endpoint policy per root, add independent element-wise/property assertions
and boundary cases, and demonstrate that each coherent topic-specific wrong
substitute fails a material invariant. Until then, strict compilation and two
passing examples are not correctness evidence.

### CAL-C01-005 — high — the audit subject and receipts omit required bindings

The subject hash itself recomputes exactly, but the hashed object does not bind
`.state/prompt-boundary.json`, `.state/lineage-screen.json`,
`.state/source-inventory.json`, raw/rejected proposal manifests, per-root
receipts, clone controls, or the normalizer/policy implementation except
indirectly through selected files. The generated tree hash explicitly excludes
`.state`. The source inventory contains counts only, with no root/file hashes
or revision identity. Per-root receipts contain a task tree hash and reference
hash but omit distinct prompt, starter, tests, metadata, provenance, negative,
compiler path/binary, and verifier-policy digests. The Docker receipt records
compiler/version text but no compiler path/hash and declares
`locked_oracle: false`.

Evidence:

- `_tree_hash` at generator lines 221-237;
- source inventory construction at lines 865-900 and raw
  `.state/source-inventory.json`;
- Docker/per-root receipts at lines 1040-1064;
- audit-subject construction at lines 1068-1076;
- `.state/audit-subject.json` and all `.state/receipts/*.json`.

Disposition: extend the next append-only cycle and per-root receipts to bind
every role and screen, immutable existing/holdout inventories, exact compiler
path/version/binary hash, policy/normalizer hashes, commands, and outcomes. Do
not overwrite cycle 001.

### CAL-C01-006 — high — lineage and contamination screens do not implement the stated checks

The curriculum requires ID, prompt, answer/reference, test, and semantic
lineage screening. The implementation checks exact candidate ID collision,
then computes one aggregate token-set Jaccard score per candidate/existing root
and per candidate/holdout. It stores only the strongest aggregate match. It
does not produce exact prompt-hash, reference-hash, test-hash, normalized
answer, API/contract, or source-lineage collision reports, and the source and
holdout inventories are not digest-bound. CAL-C01-001 demonstrates that this
normalizer misses exact observable equivalence inside the family, so its low
cross-tree scores cannot prove semantic novelty.

Evidence:

- curriculum lines 8-17 and 90-103;
- family specification lines 176-189;
- generator lines 849-870 and 974-995;
- `.state/lineage-screen.json`, `.state/benchmark-screen.json`, and
  `.state/source-inventory.json`.

Disposition: cross-tree lineage and contamination remain unresolved for all 90
roots. Add exact role/hash screens plus contract/API/reference/test-aware
semantic comparison against all 731 legacy roots, all 709 reverify roots, and
the exact digest-bound 26 holdouts. Do not infer contamination clearance from
the current thresholds.

### CAL-C01-007 — high — many public task contracts are underspecified

For most roots, the public prompt gives only a short mechanism label and the
generic statement that behavior is “part of the named mechanism” or
“deterministic.” It does not define the observable formula, parameter domain,
endpoint inclusion, start anchor, encoding, or strict/non-strict selection.
Examples include the 30E/360 convention, actual-year fraction rounding,
boundary-density weights, nth-forward boundary, fiscal boundary, capacity
vectors, and calendar-cycle checkpoints. Multiple valid industry conventions
or interpretations fit those labels. Hidden tests cannot resolve an ambiguity
that is absent from the prompt.

Evidence:

- instruction renderer at generator lines 759-799;
- per-root table at family specification lines 50-148;
- raw `.docs/instructions.md` files;
- deterministic contradictions exposed by CAL-C01-001 and CAL-C01-002.

Disposition: add a complete public, example-independent contract for every
root before treating any oracle disagreement as model error. Rerun prompt
boundary and all executable gates after regeneration.

## Root catalog and dispositions

All roots are synthetic, stateless, C++17 whole-edit tasks with `new-root`
lineage and Docker example execution. Because CAL-C01-004, CAL-C01-005,
CAL-C01-006, and CAL-C01-007 are family-wide hard gates, every listed root is
`repair-and-reverify`; no root is presently `train` or
`local_family_verified`.

### Calendar-difference metrics (30)

`calendar-signed-day-distance`, `calendar-absolute-day-gap`,
`calendar-midpoint-ordinal`, `calendar-interior-day-cardinality`,
`calendar-crossed-month-boundaries`, `calendar-crossed-year-boundaries`,
`calendar-contained-leap-days`, `calendar-contained-month-ends`,
`calendar-month-end-parity-balance`, `calendar-complete-months-between`,
`calendar-complete-years-between`, `calendar-thirty-day-convention`,
`calendar-actual-year-fraction`, `calendar-month-fragment-count`,
`calendar-year-fragment-count`, `calendar-february-day-count`,
`calendar-long-month-day-count`, `calendar-month-capacity-transition-count`,
`calendar-day-of-year-displacement`, `calendar-month-weighted-distance`,
`calendar-day-number-checksum`, `calendar-leap-year-day-count`,
`calendar-post-leap-pivot-day-count`, `calendar-century-day-count`,
`calendar-endpoint-month-length-delta`,
`calendar-endpoint-month-index-delta`, `calendar-month-end-distance-sum`,
`calendar-triangular-day-load`, `calendar-leap-cycle-index-delta`, and
`calendar-boundary-density-score`.

Additional disposition: the duplicate members identified in CAL-C01-001 must
be reduced to one canonical objective or substantively redesigned.

### Month-end transforms (30)

`monthend-add-days`, `monthend-subtract-days`,
`monthend-add-months-clamped`, `monthend-add-months-rolled`,
`monthend-add-months-eom-anchor`, `monthend-add-years-clamped`,
`monthend-add-years-march-shift`, `monthend-current-last-day`,
`monthend-next-boundary`, `monthend-previous-boundary`,
`monthend-nth-forward-boundary`, `monthend-nth-reverse-boundary`,
`monthend-quarter-boundary`, `monthend-year-boundary`,
`monthend-fiscal-boundary`, `monthend-next-leap-day`,
`monthend-previous-leap-day`, `monthend-nth-leap-day`,
`monthend-clamp-requested-day`, `monthend-roll-requested-day`,
`monthend-reflect-day`, `monthend-month-end-offset`,
`monthend-next-month-start`, `monthend-quarter-start`,
`monthend-semester-boundary`, `monthend-next-smaller-month`,
`monthend-february-boundary`, `monthend-century-cycle-clamp`,
`monthend-four-century-cycle`, and `monthend-ordinal-day-normalizer`.

Additional disposition: `monthend-next-boundary` has the concrete
upper-boundary failure in CAL-C01-003.

### Leap/month series (30)

`leapseries-month-end-partition`, `leapseries-month-start-partition`,
`leapseries-month-capacity-changes`, `leapseries-year-end-partition`,
`leapseries-leap-day-partition`, `leapseries-february-end-partition`,
`leapseries-clamped-monthly-anchor`, `leapseries-eom-monthly-anchor`,
`leapseries-rolled-monthly-anchor`, `leapseries-quarterly-anchor`,
`leapseries-annual-clamped-anchor`, `leapseries-annual-march-anchor`,
`leapseries-month-fragment-lengths`,
`leapseries-leap-status-run-lengths`, `leapseries-month-capacity-vector`,
`leapseries-leap-year-vector`, `leapseries-century-exception-vector`,
`leapseries-four-hundred-cycle-vector`, `leapseries-month-end-offsets`,
`leapseries-month-start-offsets`, `leapseries-fiscal-end-partition`,
`leapseries-capacity-run-starts`, `leapseries-semester-end-partition`,
`leapseries-century-clamped-anchors`,
`leapseries-leap-status-transitions`,
`leapseries-monthly-proration-vector`, `leapseries-leap-gap-vector`,
`leapseries-capacity-change-pairs`,
`leapseries-february-capacity-transitions`, and
`leapseries-calendar-cycle-checkpoints`.

Additional dispositions are the duplicate, value-contract, bounded-range, and
termination findings in CAL-C01-001 through CAL-C01-003.

## Duplicate, lineage, contamination, and composition summary

- Exact task IDs: 90 unique candidate IDs; no reported basename collision
  with the 731 legacy or 709 reverify roots.
- Intra-family semantic duplicates: confirmed; five excess roots across four
  equivalence groups.
- Existing-tree semantic novelty: unresolved because the current aggregate
  token-set screen is not a sound semantic or role-hash comparison.
- Official 26-root holdout: no obvious name/direct aggregate match was found,
  but exact digest-bound contamination clearance is not established.
- Composition: 30 metrics, 30 transforms, 30 series; one deterministic
  synthetic generator and one shared support/template. Difficulty and resource
  tiers are not recorded. The corpus is deliberately single-domain and
  generator-monocultural.
- Token lengths, assistant loss masks, train/validation/test split, and dataset
  rows: not applicable to this local-family-only subject.

## Required next gate

Preserve this report and cycle-001 artifacts unchanged. Route every finding to
`aider-task-family-remediation`, record repair/replace/reject decisions, change
the curriculum/owner/tests rather than generated roots, regenerate the exact
family, invalidate the old Docker and audit receipts, and run a new creator
preflight. A fresh independent audit of the new exact subject—not a remediation
self-check—must close all seven finding IDs before any passing-root count is
claimed.
