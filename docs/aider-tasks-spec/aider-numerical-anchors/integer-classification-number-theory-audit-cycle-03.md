# Integer Classification And Number Theory: Independent Audit Cycle 03

Status: `pass`. Exact retained count: 40. Dispositions: 40 `retain`
(`local_family_verified`), 0 `repair-and-reverify`, 0 `review`, 0 `reject`,
and 0 `eval-only`. No open blocker remains on the frozen subject.

This is a fresh read-only audit of local Aider task roots. It does not inherit
cycle 02's desired verdict, create JSONL rows, authorize an SFT release or
training, or claim benchmark results.

## Frozen subject and inputs

Audited root:
`.w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/integer-classification-number-theory/`

The root contained 918 regular files: 600 non-state task files (15 per root)
and 318 state, history, control, remedy, and verification files. Its cycle-03
audit-subject hash is:

`sha256:049c65f4f9dd37cedf7f15a70b7b2a1cbbd5d4f138f93a34f153015ab81bc389`

The subject hash is the SHA-256 of the sorted stream of `sha256sum` records
for every regular file below the root, with paths relative to the root. The
generator's state-excluding tree hash is
`sha256:cd8c118c907f04af98068f666f777482a2f8d29596d8e776482a1ade91585504`.
Any subsequent task, owner, policy, inventory, or receipt change makes this
report stale.

| Input/evidence | SHA-256 |
| --- | --- |
| curriculum revision 3 | `572967c6d030ff098665768d481e64405f2a58ddda05280afec264e840d869d7` |
| cycle-02 remedy specification | `6c65920a8dd8fa4a88a91c88d3fc5acca03fe6e0a85a190e6f8876561bb3e1fa` |
| owner/generator | `26ee48438cdb31750a644974d86d554cbebab2d7f1bdcf7f631fe0f86d288b83` |
| focused tests | `eefb7bf9084193a8567a4d7bb881feb2c134bae4471f26258b67eefcbc1ede27` |
| 2,500-task count plan | `1eb72a6ff9df0311b4a83712789f6259da046e83dcf26f0603e8f1860c8b6acf` |
| family manifest | `d1c523f5f8a25304f120c7b0faca99e06c074d163db04038fef9ceaca377fb9e` |
| creator preflight | `aa87de95acdb75b04ae6d349f3342a5c1bfb6d27fe49884ba572b2905a8e45a8` |
| diversity screen | `202285727021b775fdaf7687b7c6d0e5dbb4bbbecd8ddd785c5b0e32a3eeb96a` |
| cross-corpus screen | `b01973e0c3366a51c5f977c535789bf07d7918e58057abe70e6d739a9b2ae2ab` |
| source inventory | `1b7b1e42b708b9325256f3539924901ef6dc2b48517b3069fc9f77ba0b3096a6` |
| Docker sanity | `e99ccf615aaf5d72584f9369fe9235ab67988ccba7206fb4ddd7e671bfb5eb9c` |
| runtime receipt | `7f715269e4505344949ba3f9e6934cf09ecb005f290e70f91704f981313b558f` |
| cycle ledger | `6714b60151a5b31bd1221794907162478dfc0bb3a659654588b839c8a0e58f47` |

## Independent gate results

- Exactly 40 unique task IDs and roots occupy only the authorized expansion
  family. There are 40 configs and no symlinks, hardlink aliases, collisions,
  or writes into either prior generated tree.
- The 360 owner-derived header, starter, visible/private/negative test,
  reference, negative implementation, and CMake render files compared in the
  audit have zero byte mismatches. Visible prompt-role inspection found no
  private tests, reference implementation, build file, provenance, or receipt
  leakage.
- All 40 prompts publish exact `valid`, `member`, `value`, and `witness`
  semantics. The 12 predicates missing in cycle 02 are now explicit and match
  their reference behavior.
- Forty coverage ledgers bind exactly 225 private assertions: 73 valid-member,
  72 valid-nonmember, and 80 invalid-input bindings, including exactly 40
  published-upper-bound, 40 above-upper-bound, and 40 named-negative bindings.
  Each ledger names the relevant private assertion and task-specific ordering
  rule. Actual private tests byte-match the owner render.
- `k-almost-prime-membership` computes total prime-factor multiplicity without
  early exit. Its deterministic counterexample `(72,1)` is bound to
  `{valid=true, member=false, value=5, witness=3}` in both the coverage ledger
  and the dedicated negative rejection path.
- The focused suite passed independently: `15 passed in 16.70s`.
- The current Docker/runtime evidence binds the current owner and non-state
  tree. It contains 43 records: 40 tasks plus three adversarial controls. Every
  record has four passing normal tests and four passing fresh ASan/UBSan tests;
  each negative compiles, passes its public smoke, and is rejected by its
  named private counterexample. Evidence uses GCC 13.4.0, CMake 3.25.1, the
  pinned image identity, and `--network none`.
- All 780 retained-root pairs pass all seven emitted-artifact diversity
  dimensions; the maximum aggregate Jaccard score is `0.6955948298601952`.
  The constants/policy, domain-identifier, and opposite-end controls are real
  changed artifacts and all three are rejected by the production gate.
- The source inventory includes exactly all 1,440 non-state config roots in
  the two prior generated trees, with no omission or extra prior root. The
  complete screen has 3,091 sources (1,440 prior, 1,625 other expansion, and
  26 benchmark holdouts), 123,640 root comparisons, 618,200 five-surface
  comparisons, maximum Jaccard `0.30952380952380953`, and status `pass`.
- All 40 cycle-02 remedy records bind the exact invalidated cycle-02 subject,
  current generator, remedy specification, distinct before/after task-tree
  hashes, and per-task verification receipt. All 40 separate verification
  receipts hash their remedy record, bind the current task tree and Docker
  receipt, and report `verified_pending_fresh_audit`. Preserved cycle-01 and
  cycle-02 history remains separate; current records did not overwrite it.

## Root catalog and dispositions

`N4/S4` means four passing normal tests and four passing fresh sanitizer tests.
`A` is the passing assertion/contract gate, `D` the passing diversity gate,
`C` the passing duplicate/contamination gate, and `R` the passing remedy-
lineage gate.

| # | Root | Runtime | Gates | Disposition |
| ---: | --- | --- | --- | --- |
| 1 | `prime-interval-profile` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 2 | `factor-exponent-signature` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 3 | `semiprime-factor-pair` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 4 | `k-almost-prime-membership` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 5 | `squarefree-certificate` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 6 | `powerful-number-witness` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 7 | `smoothness-bound-profile` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 8 | `roughness-bound-profile` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 9 | `radical-square-kernel` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 10 | `liouville-parity` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 11 | `mobius-squarefree-sign` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 12 | `totient-density-class` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 13 | `carmichael-exponent-bound` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 14 | `multiplicative-order` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 15 | `modular-inverse` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 16 | `linear-congruence-solver` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 17 | `crt-pair-merge` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 18 | `quadratic-residue-witness` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 19 | `jacobi-symbol` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 20 | `primitive-root-verifier` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 21 | `fibonacci-index-membership` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 22 | `lucas-index-membership` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 23 | `triangular-index-membership` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 24 | `polygonal-index-membership` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 25 | `centered-polygonal-membership` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 26 | `consecutive-sum-profile` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 27 | `happy-cycle-class` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 28 | `narcissistic-base-class` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 29 | `kaprekar-split-witness` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 30 | `automorphic-suffix-class` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 31 | `harshad-quotient` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 32 | `smith-composite-class` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 33 | `emirp-reversal-class` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 34 | `palindromic-prime-base` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 35 | `additive-persistence` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 36 | `multiplicative-persistence` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 37 | `factorial-prime-valuation` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 38 | `binomial-base-trailing-zeros` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 39 | `linear-diophantine-class` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |
| 40 | `primitive-pythagorean-triple` | N4/S4 | A/D/C/R | retain (`local_family_verified`) |

## Finding dispositions

- `ICNT-AUD-001`: closed. All 12 formerly implicit member predicates are
  explicit in visible prompts and match current references.
- `ICNT-AUD-002`: remains closed. Forty coherent, task-specific negative
  algorithms are compiled, smoke-tested, and rejected by named assertions.
- `ICNT-AUD-003`: closed. The 225-assertion ledgers provide executable upper,
  above-upper, ordering/tie, member, nonmember, invalid, and named-negative
  bindings rather than prose-only claims.
- `ICNT-AUD-004`: remains closed. The current emitted-artifact screen passes
  all 780 pairs and rejects all three coherent adversarial clones.
- `ICNT-AUD-005`: closed. Screening now includes exactly all 1,440 prior
  non-state roots, including the 20 formerly skipped simulation roots, and
  fails closed on unresolved role files.
- `ICNT-AUD-006`: closed. The `72,1` exact-multiplicity counterexample returns
  `value=5`, not the former early-exit value.
- `ICNT-AUD-007`: closed. Curriculum revision 3, the cycle-02 remedy,
  generator, prompts, coverage schema, and provenance agree on the current
  contract.
- `ICNT-AUD-008`: closed. Remedy records preserve distinct pre/post hashes and
  are separately hash-bound by verification receipts while prior history is
  retained.

No new hard or soft blocker was found. Exact-ID, role-hash, five-surface
semantic, holdout, lineage, and retained-pair checks found no overwrite,
semantic duplicate, conflicting revision, or benchmark contamination. The
terminal claim is therefore exactly `local_family_verified` for these 40
roots; dataset-release gates remain out of scope.
