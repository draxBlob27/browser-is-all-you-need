# Modular Clock Normalization Fresh Independent Re-audit — Cycle 02

Status: **remediate**. The exact regenerated subject still contains **60**
retained roots, but **0** roots pass every family-wide hard gate. Root-level
dispositions are **3 repair-and-reverify**, **57 review**, **0 replaced**, and
**0 rejected**. There are **4 unresolved hard findings**: one cycle-01 finding
remains open and three new cycle-02 findings were established. The next gate is
owner-level remediation, complete regeneration and creator preflight against a
stable full expansion inventory, followed by another fresh independent audit.
This report does not admit SFT rows, authorize training, or claim benchmark
uplift.

## Frozen audit subject

This is a read-only re-audit of the generated task tree at:

`.w8-biayn/data/aider-tasks-expansion-v1/time-date/modular-clock-normalization`

| Evidence | Exact binding |
| --- | --- |
| Audit ID | `mcn-fresh-independent-reaudit-cycle-02-20260722` |
| Family ID | `aider-expansion-modular-clock-normalization-v1` |
| Retained root count | 60 |
| Generated task-file count | 840, excluding `.state/` |
| Regenerated tree hash | `sha256:3771cdc12b009190261af4ae2e8b82297c2dbf461455ba5be80132956bee8492` |
| Owner aggregate hash | `sha256:c111cc348699cfbbc7f27af35ed5ee871b6234d2c46de1902b38760ba87516f6` |
| Creator receipt internal hash | `sha256:9084ade8eb803c732604def2b43627bbb901a9a8eccca3cbda2ae6fb299b6bb2` |
| Creator receipt file SHA-256 | `sha256:c37b3b1a3cbd4f5e93ae43575f099c1dbf461474f43d1891db1d9a5b2ac7dd51` |
| Materialization manifest SHA-256 | `sha256:80180977897089e2ceeb289c109f8078d09ff4f69658abc96026a932a7383a4a` |
| Selected-candidate manifest SHA-256 | `sha256:85c87362f8661e1c989556a92f047da189ced1634fdce61a37133beb606406a3` |
| Hard-rule screen file SHA-256 | `sha256:b7c88aeab352e584bb9a25379d9dbd7b651e663335a937e515f1053c62799ecc` |
| Source-inventory file SHA-256 | `sha256:ce66ef763efdc76c9d31d1e6ab9fd945e3bd731ef120dd141aee56f8d4baa307` |
| Curriculum SHA-256 | `sha256:45a2e647586ecc79dfb266c1fc95796618fb16ad629038356f48bbd52b2f7444` |
| Focused-test SHA-256 | `sha256:3c302858f36558517998547151b01a8a8dab4c3c1208ed86433f135e5e4cd79f` |
| Cycle-01 audit SHA-256 | `sha256:a33034f728896a58a341c55ca6f55271a66c605eb211e38a513593f3d2e0ccca` |
| Cycle-01 remedy SHA-256 | `sha256:291262cb7b6792365bedecb9d51882d756ea3ce8fd55ada062145c6f371e1c24` |
| Creation cycle 10 SHA-256 | `sha256:9afdae90532912ed19cccc41fefb0e85c09bbd1b9a89927f91ef385875aec652` |
| Creation cycle 11 SHA-256 | `sha256:d91b43c0b4195e75f86eaa5f84fccb2f8133018ed424544ce8ac7acd6ca367e9` |

The tree, owner, creator-receipt internal hash, receipt-file hash, all 60 live
per-root hashes, and all three live control hashes were independently
recomputed and match the frozen creator evidence. The receipt names the
digest-pinned image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
network policy `none`, GCC 13.4.0 at `/usr/local/bin/g++` with compiler hash
`sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
and CMake 3.25.1. It records 60 times three CTests in clean normal and fresh
ASan/UBSan builds, rejection of all 60 compiled false substitutes in both
modes, and three controls times two passing CTests in both modes. That receipt
is current for the subject bytes, but its fixed tests do not cover the valid
strict-after overflow reproduced below.

## Behavior contract

| Field | Audited contract |
| --- | --- |
| Task | Implement one of 60 distinct C++17 modular normalization, wraparound, signed-offset, cyclic-range, or canonical-selection contracts. |
| Inputs | Visible instructions and exactly two task-named editable files; deterministic integer inputs only. |
| Output | Complete whole-file replacements for both editable files. |
| Invariants | Positive periods where required; Euclidean residues; deterministic order and ties; checked arithmetic; invalid input and overflow expose no partial mutation. |
| Failure behavior | Declared `nullopt`, invalid report, or atomic rollback, without undefined behavior. |
| Resource limits | Offline C++17 in the designated network-disabled Docker sanity image; explicit bounds for deliberately bounded algorithms. |
| Evaluation | Strict warnings, visible and hidden deterministic tests, compiling rejected negative fixtures, normal and fresh non-recovering sanitizer builds, seven-dimension family screening, complete generated-tree screening, and all 26 official holdouts. |
| Generalization target | Sixty genuinely distinct clean-room mechanisms in the binding count-plan cell, not domain renames, constants/policy variants, opposite-end variants, existing-tree copies, or official holdouts. |

## Independent gate results

| Gate | Independent evidence | Result |
| --- | --- | --- |
| Exact subject and receipt binding | Recomputed exact tree, owner, internal receipt, receipt file, 60 task hashes, three control hashes, manifests | pass |
| Root structure and roles | 60 unique roots, 14 task files each, two ordered whole-edit files, role-safe paths, new-root provenance | pass |
| Prompt/reference boundary | All 60 prompts rebuilt; 60 unique prompt hashes and 60 unique answer hashes; no private reference, hidden test, negative, CMake, provenance, or receipt role exposed | pass |
| Focused tests | `11 passed in 66.51s`, with bytecode and pytest cache disabled | pass |
| Recorded normal/sanitizer/negative evidence | Exact current task/control hashes bind the creator's 60 x 3 and 3 x 2 normal/fresh-sanitizer records | receipt-bound pass |
| Extreme checked arithmetic | Independent non-recovering UBSan call to `DualCycleRendezvous::next(LLONG_MAX,0,1,0,1)` | **fail** |
| Boundary coalescing | Source/contract review plus independently compiled ASan/UBSan visible and hidden tests for overlap and cover roots | pass |
| Generalized CRT core | GCD compatibility, modular inverse and checked LCM are present; billion-scale coprime test runs without enumeration | pass, but strict-after lift fails overflow gate |
| Normalization policies | Curriculum, prompts, references, and hidden tests agree that mode samples and nearest-free blocked values are Euclidean-normalized | pass |
| Recorded 1,770-pair screen | All 1,770 decisions and three control decisions reproduce exactly as recorded | syntactic reproduction only; **policy fail** |
| Anchor-free diversity challenge | Remove only the non-artifact provenance marker before applying the declared normalizer/threshold | **27 failed dimensions across 19 retained pairs** |
| Fresh-provenance clone challenge | Give each coherent control a distinct ordinary new-root semantic-anchor hash | **all three controls escape all seven dimensions** |
| Confirmed within-family semantic duplicate | HMS and angular DMS references normalize to identical public API, owned algorithm, and reference control flow | **fail** |
| Recorded all-expansion screen | Receipt says 731 legacy + 709 reverify + 1,605 non-subject expansion roots and 182,700 comparisons | recorded pass, not currently reproducible |
| Live source-inventory binding | Recomputed legacy/reverify inventories match; expansion does not and changes during a full screen | **fail** |
| Official holdouts | Receipt covers 60 x 26 = 1,560 comparisons; current 26-root checkout is complete | pass for frozen receipt subject |
| Append-only cycles | Cycle 10 preserves the failed control remediation; cycle 11 binds current tree/owner, creator-preflight path, all six source findings, and 60 retained roots | pass |
| Dataset/release/token/mask/training gates | Not requested by the local-family scope | not applicable |

The anchor-free challenge found threshold failures in 19 distinct pairs (27
pair-dimensions). Maxima include `1.0` for public API, owned algorithm, and
reference control flow, `0.916031` for mutation/selection rules, `0.888` for
invalid/boundary behavior, and `0.932773` for deterministic oracle. This does
not by itself prove all 19 pairs are semantic duplicates, but it proves that
the persisted all-distinct result is created by provenance rather than task
artifacts and that those pairs require real adjudication after the evaluator
is repaired.

## Stable finding dispositions

### `cycle-01/family/signed-modular-overflow` — remains open

- Disposition: `repair-and-reverify` for
  `mcn-dual-cycle-rendezvous`; all other cycle-01 reproduced arithmetic
  examples reviewed in this cycle are closed by the new helpers and checked
  operations.
- Exact counterexample: compile the current `.meta/example.cpp` under C++17
  with `-fsanitize=undefined -fno-sanitize-recover=all`, set
  `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`, and call
  `DualCycleRendezvous::next(LLONG_MAX,0,1,0,1)`.
- Observed result: compile succeeds; execution terminates at the current
  strict-after expression `gap/l+1` because `LLONG_MAX + 1` overflows.
- Contract result: no representable tick is strictly greater than
  `LLONG_MAX`, so the function must return the declared empty/overflow result,
  not execute undefined behavior.
- Required closure: compute the ceiling increment without an unchecked `+1`,
  add the exact extreme to the production hidden oracle, regenerate, and
  obtain current normal/fresh non-recovering sanitizer and negative evidence.

### `cycle-01/cyclic-range-family/boundary-coalescing-oracle-drift` — closed

The curriculum, prompt, reference, and deterministic tests now agree on one
wrapped piece for period/zero-connected intersections and covers. Both roots'
visible and hidden tests independently pass under ASan/UBSan with non-recovery.

### `cycle-01/mcn-dual-cycle-rendezvous/crt-mechanism-not-implemented` — closed

The retained reference now uses generalized non-coprime CRT rather than a
linear residue scan and includes compatible, incompatible, and billion-scale
period evidence. This closure does not close the separate strict-after
overflow above.

### `cycle-01/contracts/normalization-policy-drift` — closed

`mcn-modular-mode-selector` normalizes every sample residue, and
`mcn-nearest-free-phase` normalizes and uniques blocked residues under the
explicit one-million period bound. Curriculum, visible prompt, reference, and
tests agree; both roots' visible and hidden tests independently pass under
ASan/UBSan.

### `cycle-01/family/expansion-semantic-screen-omitted` — implementation fixed, evidence superseded

The owner now enumerates every non-subject expansion root and the frozen
receipt records the intended 182,700 comparisons. The original omission is
fixed, but the new cycle-02 source-inventory-drift finding prevents the frozen
result from closing the current full-tree contamination gate.

### `cycle-01/family/passing-preflight-cycle-unrecorded` — closed

Cycles 01-09 remain present. Cycle 10 records the failed opposite-policy
control remediation attempt. Cycle 11 binds the current regenerated tree,
owner, focused test, grader policy, creator-preflight path, 60 retained IDs,
and all six source findings with state
`remediated_creator_preflight_pass`.

## New cycle-02 findings

### `cycle-02/family/provenance-anchor-diversity-bypass`

- Severity: hard diversity and adversarial-control policy failure.
- Disposition: family `repair-and-reverify`; every retained pair remains
  `review` until the repaired policy is applied.
- Evidence: `_similarity` detects differing
  `MCN_SEMANTIC_ANCHOR=sha256:...` marker values and returns
  `min(raw_similarity, 0.50)`. Every ordinary retained root has different
  anchors, so no retained pair can reach the declared rejection threshold
  `0.84`, regardless of artifact similarity. The maximum persisted score in
  every dimension is exactly `0.50`.
- Control failure: controls copy their base root's anchors. Replacing only the
  marker with an ordinary distinct new-root anchor makes each domain-rename,
  constants/policy, and opposite-end control score `0.50` in all seven
  dimensions and escape with zero failed dimensions.
- Anchor-free result: applying the existing normalizer and thresholds to the
  actual dimension material without the provenance line yields 27 failures
  across 19 retained pairs.
- Required closure: provenance may bind evidence but must not force a
  diversity verdict. Remove the cap, make every control use realistic fresh
  new-root provenance, rerun and adjudicate all 1,770 pairs from artifacts,
  and bind the new policy/results into a fresh receipt.

### `cycle-02/mcn-signed-hms-normalizer__mcn-angular-dms-normalizer/domain-renamed-semantic-duplicate`

- Severity: hard no-padding/no-domain-rename failure.
- Disposition: `repair-and-reverify` for both roots until remediation selects
  one canonical contract and replaces the other with a genuinely new backfill.
- Evidence: after the owner's declared comment/string/literal/identifier
  normalization, this pair scores `1.0` for public API, owned algorithm, and
  reference control flow; `0.916031` for mutation/selection rules; `0.849206`
  for boundary behavior; and `0.88` for the deterministic oracle. Direct
  source review confirms the same checked `((outer * 60) + middle) * 60 +
  inner`, floor-divide by caller-supplied outer cycle, and base-60 expansion.
  Only the time/angle nouns, examples, and false-substitute emphasis differ.
- Required closure: retain at most one, preserve explicit lineage, author a
  mechanism-distinct backfill to keep the required count at 60, regenerate,
  and run the full loop. Renaming, changing constants, or moving the endpoint
  is not remediation.

### `cycle-02/family/source-inventory-drift`

- Severity: hard duplicate/contamination evidence-binding failure.
- Disposition: all roots `review` until a stable full inventory is screened
  and receipt-bound.
- Frozen evidence: 731 legacy, 709 reverify, and 1,665 expansion roots (60
  subject plus 1,605 non-subject), with expansion inventory hash
  `sha256:eb291ea432e796734c1f8fd2938bf97e8e26a8161032603fbfa617cd5abeaa7a`.
- Independent live evidence: legacy and reverify still match their frozen
  hashes. Two consecutive live expansion snapshots were mutually stable at
  the same 1,665 count but hash
  `sha256:c5ce42d5b5d875cbac5b56ff58a9ea8204c2b21196421274ecd5da311f357ce5`.
  The path `numerical-anchors/rational-complex-value-arithmetic/rational-weighted-median`
  was absent and
  `numerical-anchors/rational-complex-value-arithmetic/rational-amortization-schedule`
  was new, while numerous non-subject task hashes differed.
- A subsequent complete live 182,700-comparison attempt correctly failed
  closed with `source_inventory_stale` at
  `state-concurrency/deterministic-parallel-reductions/dpr-affine-compose-summary`,
  proving the external inventory was changing during audit.
- Required closure: wait for the non-subject expansion tree to settle, freeze
  the exact live inventory, rerun all comparisons without drift, regenerate
  creator evidence/receipt against those hashes, append the next cycle, and
  fresh-audit it. A recorded count without reproducible hashes is insufficient.

## Root audit catalog

`repair-and-reverify` takes precedence over the family-wide `review` status.
The 57 review roots have no additional root-specific defect established here,
but neither the diversity nor full expansion-contamination gate is currently
valid.

| # | Root | Disposition | Basis |
| ---: | --- | --- | --- |
| 1 | `mcn-euclidean-residue-ledger` | review | family diversity/inventory gates |
| 2 | `mcn-balanced-phase-residue` | review | family diversity/inventory gates |
| 3 | `mcn-anchored-cycle-window` | review | family diversity/inventory gates |
| 4 | `mcn-directed-phase-distance` | review | family diversity/inventory gates |
| 5 | `mcn-affine-phase-map` | review | family diversity/inventory gates |
| 6 | `mcn-linear-congruence-rendezvous` | review | family diversity/inventory gates |
| 7 | `mcn-paired-clock-crt` | review | family diversity/inventory gates |
| 8 | `mcn-tick-rate-resampler` | review | family diversity/inventory gates |
| 9 | `mcn-fractional-phase-accumulator` | review | family diversity/inventory gates |
| 10 | `mcn-mixed-period-flattener` | review | family diversity/inventory gates |
| 11 | `mcn-signed-hms-normalizer` | repair-and-reverify | confirmed semantic duplicate pair |
| 12 | `mcn-film-timecode-carry` | review | family diversity/inventory gates |
| 13 | `mcn-music-grid-normalizer` | review | family diversity/inventory gates |
| 14 | `mcn-shift-slot-subtick` | review | family diversity/inventory gates |
| 15 | `mcn-angular-dms-normalizer` | repair-and-reverify | confirmed semantic duplicate pair |
| 16 | `mcn-heterogeneous-wheel-carry` | review | family diversity/inventory gates |
| 17 | `mcn-quotient-remainder-duration` | review | family diversity/inventory gates |
| 18 | `mcn-carry-trace-normalizer` | review | family diversity/inventory gates |
| 19 | `mcn-bounded-era-phase` | review | family diversity/inventory gates |
| 20 | `mcn-sparse-unit-canonicalizer` | review | family diversity/inventory gates |
| 21 | `mcn-claimed-wrap-validator` | review | family diversity/inventory gates |
| 22 | `mcn-monotone-phase-unwrapper` | review | family diversity/inventory gates |
| 23 | `mcn-bounded-jump-unwrapper` | review | family diversity/inventory gates |
| 24 | `mcn-directed-phase-unwrapper` | review | family diversity/inventory gates |
| 25 | `mcn-nearest-anchor-unwrapper` | review | family diversity/inventory gates |
| 26 | `mcn-sensor-phase-aligner` | review | family diversity/inventory gates |
| 27 | `mcn-gap-aware-phase-unwrapper` | review | family diversity/inventory gates |
| 28 | `mcn-reset-aware-phase-trace` | review | family diversity/inventory gates |
| 29 | `mcn-jitter-filtered-unwrapper` | review | family diversity/inventory gates |
| 30 | `mcn-modular-delta-codec` | review | family diversity/inventory gates |
| 31 | `mcn-anchored-arc-splitter` | review | family diversity/inventory gates |
| 32 | `mcn-cyclic-overlap-measurer` | review | family diversity/inventory gates |
| 33 | `mcn-periodic-cover-coalescer` | review | family diversity/inventory gates |
| 34 | `mcn-circular-gap-complement` | review | family diversity/inventory gates |
| 35 | `mcn-minimum-covering-arc` | review | family diversity/inventory gates |
| 36 | `mcn-boundary-aware-window` | review | family diversity/inventory gates |
| 37 | `mcn-anchor-relative-clipper` | review | family diversity/inventory gates |
| 38 | `mcn-shifted-reservation-normalizer` | review | family diversity/inventory gates |
| 39 | `mcn-circular-bin-rebalancer` | review | family diversity/inventory gates |
| 40 | `mcn-cyclic-range-subtractor` | review | family diversity/inventory gates |
| 41 | `mcn-offset-day-quotient-board` | review | family diversity/inventory gates |
| 42 | `mcn-offset-graph-consistency` | review | family diversity/inventory gates |
| 43 | `mcn-canonical-offset-table` | review | family diversity/inventory gates |
| 44 | `mcn-inverse-offset-resolver` | review | family diversity/inventory gates |
| 45 | `mcn-offset-roundtrip-auditor` | review | family diversity/inventory gates |
| 46 | `mcn-staged-offset-transition` | review | family diversity/inventory gates |
| 47 | `mcn-variable-period-segment-map` | review | family diversity/inventory gates |
| 48 | `mcn-dual-cycle-rendezvous` | repair-and-reverify | non-recovering valid-input overflow |
| 49 | `mcn-reference-window-projector` | review | family diversity/inventory gates |
| 50 | `mcn-offset-equivalence-grouper` | review | family diversity/inventory gates |
| 51 | `mcn-circular-l1-median` | review | family diversity/inventory gates |
| 52 | `mcn-squared-phase-medoid` | review | family diversity/inventory gates |
| 53 | `mcn-modular-mode-selector` | review | family diversity/inventory gates |
| 54 | `mcn-shortest-enclosing-arc` | review | family diversity/inventory gates |
| 55 | `mcn-largest-gap-clusterer` | review | family diversity/inventory gates |
| 56 | `mcn-nearest-free-phase` | review | family diversity/inventory gates |
| 57 | `mcn-minimal-cycle-rotation` | review | family diversity/inventory gates |
| 58 | `mcn-rotation-invariant-deltas` | review | family diversity/inventory gates |
| 59 | `mcn-dihedral-phase-canonicalizer` | review | family diversity/inventory gates |
| 60 | `mcn-modular-permutation-auditor` | review | family diversity/inventory gates |

## Duplicate, lineage, and contamination report

- Exact within-family task IDs, prompt hashes, and answer hashes are unique for
  all 60 roots. Every selected provenance record declares clean-room
  `new-root` lineage with no parent, and no candidate ID collides with the
  frozen 731-root legacy or 709-root reverify inventories.
- The persisted 1,770-pair ledger is complete as a pair enumeration, but its
  all-distinct decisions are invalidated by the provenance-anchor cap. The
  three persisted controls are coherent and behavior-tested, but they are not
  valid fresh-root controls because they inherit base provenance.
- The HMS/DMS pair is a confirmed within-family semantic duplicate under the
  creator's own no-domain-rename rule. It cannot contribute two passing roots
  to the required count.
- The complete current all-expansion comparison cannot be reproduced while
  non-subject roots change. No absence-of-duplicate claim is made from the
  stale 182,700-comparison receipt.
- The frozen official-holdout record contains all 26 expected roots and 1,560
  comparisons; its strongest score is low (`0.0694737`, periodic cover versus
  `crypto-square`). No official-holdout match was established.
- No ancestor/correction conflict, benchmark answer leakage, private-reference
  prompt leakage, or conflicting same-ID target was found inside the exact
  subject.

## Corpus composition and limitations

The subject has three equal 20-root tranches: normalization/carry;
sequence-unwrapping/cyclic ranges; and signed offsets/rendezvous/canonical
selection. Every retained root is a synthetic clean-room, two-file whole-edit
C++17 task. Uniform local provenance is appropriate for the requested family
but is not a future training-mixture or release claim. Tokenizer length, masks,
splits, dataset finalization, producer verification, export, consumer
verification, training, and model uplift are outside this request and were not
inferred.

## Verdict

`remediate`. The exact regenerated bytes and most targeted cycle-01 remedies
are well bound, but the family is not `local_family_verified` and none of the
60 roots may be counted as passing the complete gate set. The dual-cycle root
still executes signed-overflow undefined behavior on a valid extreme input;
the diversity evaluator and clone controls are provenance-dependent and miss
a confirmed domain-renamed duplicate; and the complete expansion inventory is
changing, so its contamination receipt is stale. Preserve this report,
remediate through the owner, replace/backfill as required to restore 60
genuinely distinct roots, regenerate and preflight against a stable source
inventory, then conduct a new fresh independent audit.
