# Integer Classification And Number Theory: Independent Audit Cycle 02

Status: `not_completed`. Exact retained count: 40. Dispositions: 40
`repair-and-reverify`, 0 `train`, 0 `review`, 0 `reject`, 0 `eval-only`.
Normal/fresh-sanitizer evidence passes, but every root remains blocked by the
required upper-bound oracle gate and the family has additional prompt,
correctness, inventory, and evidence-integrity blockers.

This report is a fresh read-only audit. It does not inherit cycle 01's verdict,
and it does not authorize JSONL generation, an SFT release, training, or a
benchmark claim.

## Exact subject and inputs

Audited root:
`.w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/integer-classification-number-theory/`

The root contained 654 regular files: 560 task files (14 per root) and 94
state/history/control/remedy files. Its cycle-02 audit-subject hash is:

`sha256:5dec634b096d9133a0ea4744433edaf3043fc487ae1faa6d1263082fc0bf2ef7`

The subject hash is the SHA-256 of the sorted stream of `sha256sum` records for
every regular file below the root, with paths relative to the root. The
generator's non-state tree hash is
`sha256:0376f96f5e9fdfa5d4fee9ac0546a80fa76a9105155fe8e6b7e45662b5735801`.
Any subsequent task, owner, policy, inventory, or receipt change makes this
report stale.

| Input/evidence | SHA-256 |
| --- | --- |
| curriculum | `18543211047ce6d1061c5dff83f4373edc7f704ea6abb9bb259173f273ceb2a4` |
| remedy specification | `6693f1b3ed694775435fec8f945656edbb323f40d9ddd7b607cb65162269e637` |
| owner/generator | `b7a51c4e38e46176c4b82c2d10edcb76cd29ec9c6db545e4436499525c87fe2e` |
| focused tests | `82786c345979897afde0eb9c1607eb40bdc611686d18e2cbf3b0f5fb6a07aafb` |
| family manifest | `581961ffdb415c300ab5aa6af0cbca3fc8d3ae8460b8f09a906e23ffa52ecac4` |
| creator preflight | `508ddbb604e3aee0ca472076a723860ae77f4a485293f21e815f097510c37eb7` |
| diversity screen | `7793bbbe1c2c218f9502d76065c9ac99d2d4010658b6480b43eb9114184755d4` |
| cross-corpus screen | `e591a589d023f1ddfdf8e64117f7fa7e67b2591cdec313ad5657125bf827149a` |
| source inventory | `146cbc98a1bde9608925627c9259088439acb36dc431a45922428bbc713e4105` |
| Docker sanity | `96e60e1bb770893c8143f27c5d11fcf846ac165b6bf4f2d710b3c8f7d48afdba` |
| runtime receipt | `50c7f529e0582274f83ed884855347525937d16115e36c8d30efeb5f9ad88dda` |
| cycle ledger | `207315c9ff6dc0262427330ca400dba704dc4511e4c120fe52cbdb36cda6d36d` |

## Contract and confirmed evidence

The task contract is two-file whole-edit C++17 implementation from visible
docs and starters, preserving each namespace, signature, and total
`{valid,member,value,witness}` result. Invalid arguments must return
`{false,false,-1,-1}`; valid members and non-members must return the exact
public diagnostics. Arithmetic is bounded signed 64-bit integer arithmetic;
floating point, external processes, hard-coded examples, and third-party
number-theory libraries are forbidden.

Confirmed independently:

- Exactly 40 unique IDs and roots exist under the authorized expansion path;
  no task was written into either prior tree. There are 40 configs, 40
  revision-2 provenance records, 40 coverage ledgers, no symlinks, no hardlink
  aliases, and no ID collision against the prior or other expansion roots.
- All 40 actual references, private tests, visible tests, and negative sources
  byte-match the current owner's corresponding generated render functions.
- Prompt-role inspection found zero private/reference/CMake/provenance/receipt
  leakage in the visible docs and editable starters.
- The focused suite passed independently: `13 passed in 16.77s`.
- The Docker receipt is current for the non-state tree and owner. It records 40
  task roots and three controls, four normal and four fresh ASan/UBSan tests per
  root/control, all passing, under GCC 13.4.0, CMake 3.25.1, the pinned image
  digest, and `--network none`.
- All 40 negatives are now task-specific mutated algorithms, compile cleanly,
  pass the public case, and fail a private assertion. No cycle-01
  visible-example hardcode remains. ICNT-AUD-002 is closed on this subject.
- Diversity is derived from emitted docs/header/reference/private-test/
  coverage/negative content rather than provenance. All 780 pairs pass; maximum
  aggregate Jaccard is 0.681805. Three coherent controls are rejected. Manual
  review of the highest-related clusters found shared concepts with distinct
  intended contracts. ICNT-AUD-004 is closed on this subject.
- Independent exact screening found 0 candidate ID collisions and 0 exact
  matches between 320 candidate role-file hashes and 34,801 unique files in
  the compared prior/expansion/holdout trees. This does not close the omitted
  inventory finding below.

## Root catalog

`N4/S4` is current passing normal/sanitizer discovery. `U` is the missing
published-upper-bound assertion (ICNT-AUD-003), `M` is an unspecified member
predicate (ICNT-AUD-001), and `R` is a reference/prompt contradiction
(ICNT-AUD-006). Family findings ICNT-AUD-005, ICNT-AUD-007, and
ICNT-AUD-008 apply to every retained root.

| # | Root | Runtime | Open root gates | Disposition |
| ---: | --- | --- | --- | --- |
| 1 | `prime-interval-profile` | N4/S4 | U, M | repair-and-reverify |
| 2 | `factor-exponent-signature` | N4/S4 | U, M | repair-and-reverify |
| 3 | `semiprime-factor-pair` | N4/S4 | U | repair-and-reverify |
| 4 | `k-almost-prime-membership` | N4/S4 | U, R | repair-and-reverify |
| 5 | `squarefree-certificate` | N4/S4 | U | repair-and-reverify |
| 6 | `powerful-number-witness` | N4/S4 | U | repair-and-reverify |
| 7 | `smoothness-bound-profile` | N4/S4 | U | repair-and-reverify |
| 8 | `roughness-bound-profile` | N4/S4 | U | repair-and-reverify |
| 9 | `radical-square-kernel` | N4/S4 | U, M | repair-and-reverify |
| 10 | `liouville-parity` | N4/S4 | U, M | repair-and-reverify |
| 11 | `mobius-squarefree-sign` | N4/S4 | U, M | repair-and-reverify |
| 12 | `totient-density-class` | N4/S4 | U | repair-and-reverify |
| 13 | `carmichael-exponent-bound` | N4/S4 | U, M | repair-and-reverify |
| 14 | `multiplicative-order` | N4/S4 | U | repair-and-reverify |
| 15 | `modular-inverse` | N4/S4 | U | repair-and-reverify |
| 16 | `linear-congruence-solver` | N4/S4 | U | repair-and-reverify |
| 17 | `crt-pair-merge` | N4/S4 | U | repair-and-reverify |
| 18 | `quadratic-residue-witness` | N4/S4 | U | repair-and-reverify |
| 19 | `jacobi-symbol` | N4/S4 | U, M | repair-and-reverify |
| 20 | `primitive-root-verifier` | N4/S4 | U | repair-and-reverify |
| 21 | `fibonacci-index-membership` | N4/S4 | U | repair-and-reverify |
| 22 | `lucas-index-membership` | N4/S4 | U | repair-and-reverify |
| 23 | `triangular-index-membership` | N4/S4 | U | repair-and-reverify |
| 24 | `polygonal-index-membership` | N4/S4 | U | repair-and-reverify |
| 25 | `centered-polygonal-membership` | N4/S4 | U | repair-and-reverify |
| 26 | `consecutive-sum-profile` | N4/S4 | U, M | repair-and-reverify |
| 27 | `happy-cycle-class` | N4/S4 | U | repair-and-reverify |
| 28 | `narcissistic-base-class` | N4/S4 | U | repair-and-reverify |
| 29 | `kaprekar-split-witness` | N4/S4 | U | repair-and-reverify |
| 30 | `automorphic-suffix-class` | N4/S4 | U | repair-and-reverify |
| 31 | `harshad-quotient` | N4/S4 | U | repair-and-reverify |
| 32 | `smith-composite-class` | N4/S4 | U | repair-and-reverify |
| 33 | `emirp-reversal-class` | N4/S4 | U | repair-and-reverify |
| 34 | `palindromic-prime-base` | N4/S4 | U | repair-and-reverify |
| 35 | `additive-persistence` | N4/S4 | U, M | repair-and-reverify |
| 36 | `multiplicative-persistence` | N4/S4 | U, M | repair-and-reverify |
| 37 | `factorial-prime-valuation` | N4/S4 | U, M | repair-and-reverify |
| 38 | `binomial-base-trailing-zeros` | N4/S4 | U, M | repair-and-reverify |
| 39 | `linear-diophantine-class` | N4/S4 | U | repair-and-reverify |
| 40 | `primitive-pythagorean-triple` | N4/S4 | U | repair-and-reverify |

## Open findings

### ICNT-AUD-001 — member semantics remain non-public for 12 roots

Severity: hard prompt-solvability gate. Disposition: repair and reverify the 12
listed roots.

Every prompt now defines `value` and `witness`, but `member` is still defined
only as true when "the classification in the first paragraph holds." The first
paragraph does not state a boolean classification for these roots:

`prime-interval-profile`, `factor-exponent-signature`,
`radical-square-kernel`, `liouville-parity`, `mobius-squarefree-sign`,
`carmichael-exponent-bound`, `jacobi-symbol`, `consecutive-sum-profile`,
`additive-persistence`, `multiplicative-persistence`,
`factorial-prime-valuation`, and `binomial-base-trailing-zeros`.

The hidden reference choices are material and sometimes arbitrary: total
multiplicity greater than one, radical equal to `n`, Liouville sign `+1`,
nonzero Möbius value, lambda less than `n-1`, Jacobi value exactly `+1`, at
least one representation, persistence thresholds of two/three rounds,
positive factorial valuation, and a positive trailing-zero count. These exact
predicates must be stated in the visible prompt. Cycle-01 output-field prose
alone does not make them inferable.

### ICNT-AUD-003 — all 40 requirement ledgers overclaim oracle coverage

Severity: hard deterministic-oracle gate. Disposition: repair and reverify all
40 roots.

Branch coverage improved: every private test now has a member, non-member, and
invalid case, with 3–5 assertions per root (144 total). However, the remedy
specification requires every root to assert its published upper bound and its
material boundary/tie behavior. No private test contains the common published
`1000000000` or `1000000` upper values, and inspection of the remaining
task-specific maxima likewise found no per-root published-upper-bound case.
The coverage JSON stores the output-field prose under `ordering_and_ties` and
marks status `covered`; it does not bind a boundary/tie requirement to a
specific assertion. These are example ledgers, not complete requirement
ledgers or an independent property oracle.

Add exact named assertions for the valid upper surface (and invalid value just
beyond it where representable), task-specific ordering/ties, and the named
negative counterexample. Bind each requirement to its private assertion rather
than to prose, then regenerate all runtime evidence.

### ICNT-AUD-005 — 20 reserved prior roots are silently absent from screening

Severity: hard uniqueness/contamination gate. Disposition: repair the family
screen and reissue its inventory receipt.

The receipt reports 1,420 prior-tree sources, but the two prior trees contain
1,440 unique config roots. `_surface_record` returns `None` and the caller
silently skips 20 roots whose config names `.meta/task_visible_test.cpp` while
their visible test is at the root. All are reserved robot-simulation roots:

`sim-airport-tug`, `sim-construction-hauler`, `sim-drone-delivery`,
`sim-factory-inspector`, `sim-farm-irrigator`, `sim-firefighter-bot`,
`sim-greenhouse-cart`, `sim-harbor-crane`, `sim-hospital-courier`,
`sim-library-sorter`, `sim-mars-rover-energy`, `sim-museum-guide`,
`sim-ocean-survey`, `sim-orchard-harvester`, `sim-recycling-sorter`,
`sim-search-and-rescue`, `sim-snowplow-route`,
`sim-space-station-repair`, `sim-subway-maintenance`, and
`sim-warehouse-picker`.

No positive collision with this numerical family was observed, but omission is
not a passing comparison. The screen must fail closed or normalize known role
layouts and include all 1,440 reserved roots in the digest-bound inventory.

### ICNT-AUD-006 — `k-almost-prime-membership` contradicts its prompt

Severity: hard correctness gate. Task: `k-almost-prime-membership`.
Disposition: repair and reverify.

The prompt says `value` is the *exact total* prime-factor multiplicity. The
reference stops as soon as its running total exceeds `k` and returns that
partial total. Deterministic counterexample: for `n=72, k=1`, the exact total
is five (`2^3 * 3^2`), while the reference returns after the factor 2 with
`value=3`. Current tests do not contain this case. Either compute the exact
total before returning or change the public contract; the curriculum's stated
independent oracle favors computing the exact total.

### ICNT-AUD-007 — curriculum revision 1 conflicts with the revision-2 remedy

Severity: hard source-contract integrity gate. Scope: family.
Disposition: repair the curriculum and regenerate.

The manifest and provenance continue to name the unchanged curriculum as the
source. That document still labels itself revision 1 and says every negative
is a "precomputed-visible-example substitute" with the old three-example
private-test contract. The remedy specification declares revision 2, removes
generic hardcodes, and requires member/non-member/invalid/upper-bound/tie
coverage. Both are bound inputs and no precedence rule resolves the conflict.
Update the owning curriculum to the implemented revision-2 contract so the raw
source, remedy, generator, and generated provenance agree.

### ICNT-AUD-008 — all 40 remedy records misbind remediation lineage

Severity: hard evidence-integrity gate. Scope: all remedy records.
Disposition: preserve the existing records and issue corrected immutable
records during the next regeneration.

All 40 records claim generator revision
`sha256:c6602bfd6c822232e0e9b9c4941ace83194560815ac0e52b4af521f3627f772b`,
while the generator that owns this exact tree is
`sha256:b7a51c4e38e46176c4b82c2d10edcb76cd29ec9c6db545e4436499525c87fe2e`.
All 40 also have identical `tree_hash_before` and `tree_hash_after`, because
later full regenerations overwrote the original remedy records. They therefore
do not preserve the pre-remediation-to-post-remediation lineage they purport to
verify. A current tree hash elsewhere does not repair a false immutable remedy
record.

## Closed prior findings and duplicate/contamination report

- ICNT-AUD-002: closed; 40 named coherent negatives are current and executed.
- ICNT-AUD-004: closed; emitted-artifact diversity and controls are current.
- Exact task IDs, prompt/reference/test role-file hashes, and current retained
  pair identities show no duplicate or conflicting revision.
- Related factor, sequence, figurate, and digit families are shared-concept,
  distinct intended contracts rather than detected duplicates.
- Holdout count is 26; no benchmark-content match was observed. The claim is
  still not admissible until ICNT-AUD-005 includes every reserved source.
- All 40 roots remain declared `new-root`; no ancestor/replacement conflict was
  observed.

## Composition and scope

The corpus remains 40 repository-authored, clean-room, CC0-1.0, synthetic,
stateless C++17 whole-edit roots: 13 prime/factor-function, seven modular/
congruence, six sequence/figurate, ten digit/base, and four valuation/equation
tasks. Verification is network-disabled Docker build/test plus fresh
ASan/UBSan and named negative execution. The common result/prompt/CMake shape is
a format monoculture, but the intended algorithms are varied.

Tokenizer, assistant-loss masks, JSONL row lengths, split manifests, and model
validation are not applicable: the authorized endpoint is local task roots,
not a dataset release.

## Terminal decision

This exact subject is `not_completed` and cannot be marked
`local_family_verified`. Open findings are ICNT-AUD-001, ICNT-AUD-003,
ICNT-AUD-005, ICNT-AUD-006, ICNT-AUD-007, and ICNT-AUD-008. Preserve this
report unchanged; repair the curriculum/owner/tests and evidence records,
regenerate the complete 40-root family, rerun creator and network-disabled
normal/fresh-sanitizer preflight, and submit the new exact subject to another
fresh independent audit.
