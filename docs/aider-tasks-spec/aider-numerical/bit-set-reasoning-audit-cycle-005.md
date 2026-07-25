# Independent audit: bit and set reasoning, cycle 005

## Verdict

**Status: `not_completed`. Retained passing roots: 0 of 40.** The exact
cycle-005 subject
`sha256:d4c1dd7255821b2792fcb05d00fcad4c810ee815ac887966c90496e9508b9922`
and non-state family tree
`sha256:072af9973e6ca1bb12876530b9ce034acff5a8c68cc1652e5565840b70d12cd5`
reproduce, including the subject's artifact, receipt, remedy, and control-tree
bindings. The cycle-004 public-header and visible/private-oracle diversity
defect is materially repaired: a strict lexer finds 40 header shapes and 40
combined-test shapes, with zero equal pairs and all 780 position-aware pair
decisions passing. Two family blockers remain. First, the same independent
lexer finds three failing topic-negative-fixture pairs after numeric suffixes
are correctly erased as part of their literals. Second, the exact external
source inventory was stale at audit start because 43 other expansion roots had
changed semantic hashes. All 40 roots therefore remain
`repair-and-reverify`; none is `local_family_verified`.

## Behavior contract used for this audit

Each retained root must expose a prompt-solvable C++17 whole-file task whose
reference implements its published bit/set mechanism for every valid input and
rejects every invalid input. The public API, owned algorithm, selection rules,
boundary behavior, reference control flow, deterministic oracle, and coherent
wrong substitute must each be materially distinct for all 780 unordered pairs
after comments, strings, character/numeric literals (including suffixes), task
names, namespace/function names, field names, `std`, fixed-width typedef names,
and every other non-language identifier are erased. Contract prose does not
count as emitted structure. Exact legacy, reverify, other-expansion, and 26
official-holdout inputs must be bound to the subject.

## Recomputed subject and executable evidence

- Canonical recomputation of the subject JSON matches the claimed subject
  hash. All 14 scalar artifact bindings, 40 retained receipt hashes, 80 remedy
  hashes, two invalidated Morton receipt hashes, and three control-tree hashes
  match current bytes. The tree has exactly 40 roots and 520 non-state files,
  13 per root.
- All 40 prompts were independently rebuilt. Their hashes and editable-file
  order match the bound records; lengths are 3,381--5,309 characters. No CMake,
  provenance, reference, hidden test, negative fixture, `.meta`, or `.state`
  material leaks into a prompt.
- The targeted-case catalog has exactly 40 records and 80 cases. Each visible
  or private request and expected triple occurs in its designated emitted
  test. The current Docker receipt binds those exact test hashes and records
  both suites passing in normal and sanitizer modes. The algorithm cores and
  previously audited boundary fixes are unchanged by the API-layout remedy.
- The Docker receipt binds both owner-side and mounted trees to the current
  tree hash. It records 40 normal and 40 fresh ASan/UBSan task records, exactly
  two discovered CTests per task, and nonzero visible/private negative exits in
  both modes. It also records all three controls in both modes, with two tests
  and both negatives rejected. The network-disabled image is
  `sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`;
  `/usr/local/bin/c++` is GCC 13.4.0 with digest
  `sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`;
  CMake is 3.25.1.
- The focused audit invocation, with pytest cache and bytecode writes disabled,
  reports `6 passed`.

## Independent emitted-structure screen

The audit lexer removes comments, strings, character and numeric literals with
their suffixes, and maps every non-C++-keyword identifier—including `std` and
all fixed-width typedef spellings—to one neutral identifier token. It retains
only C++ language keywords, operators, and punctuation. Position-aware trigram
sets use the same published ceilings, but are reconstructed independently from
the emitted files and never use curriculum or contract prose.

| Dimension | Strict shapes | Equal pairs | Failing pair decisions | Maximum overlap |
| --- | ---: | ---: | ---: | ---: |
| public header | 40 | 0 | 0 | 0.746479 |
| owned algorithm/reference core | 40 | 0 | 0 | 0.561702 |
| core plus visible selection rules | 40 | 0 | 0 | 0.350929 |
| core plus private boundary rules | 40 | 0 | 0 | 0.350929 |
| reference control flow | 40 | 0 | 0 | 0.561702 |
| combined visible/private oracle | 40 | 0 | 0 | 0.267016 |
| topic negative fixture | 38 | 2 | 3 | 1.000000 |

The negative-fixture failures are exact, not prose judgments:

- `bit-fold-parity` / `bit-prefix-rank`: identical strict shape, overlap
  1.000000, symmetric difference 0;
- `set-packed-exact-cover-count` / `set-packed-transitive-closure`: identical
  strict shape, overlap 1.000000, symmetric difference 0;
- `bit-gray-encoding` / `bit-width-reversal`: overlap 0.951456 and symmetric
  difference 10, failing the published strict `< 0.95` ceiling.

The production/focused lexer leaves literal suffixes such as `U`/`ULL` as
separate identifier tokens after replacing only the numeric portion. Those
tokens manufacture the recorded distinctions. A literal's suffix is part of
the literal and cannot supply task-family diversity.

## Audit-start source-inventory reconciliation

This was the first audit operation. Exact counts match: 3,065 external roots
(731 legacy, 709 reverify, 1,625 other expansion), 40,657 semantic files, and
122,600 candidate/external comparisons. There are zero live-only or
recorded-only keys; task IDs, config hashes, and semantic file counts match.
However, 43 other expansion roots have changed semantic tree hashes. The
subject records aggregate
`sha256:b53638e9bd21befd028f01d614a1f6276e890897d04cd24ed7d4b73157bb31cb`;
the audit-start live aggregate is
`sha256:466fdfa8b198af709a17ee4f0cfc5366da816ec9752b65b846c3f3c64671ce6b`.

The exact changed paths are all 40 roots under
`numerical-anchors/integer-classification-number-theory/`:
`additive-persistence`, `automorphic-suffix-class`,
`binomial-base-trailing-zeros`, `carmichael-exponent-bound`,
`centered-polygonal-membership`, `consecutive-sum-profile`, `crt-pair-merge`,
`emirp-reversal-class`, `factor-exponent-signature`,
`factorial-prime-valuation`, `fibonacci-index-membership`, `happy-cycle-class`,
`harshad-quotient`, `jacobi-symbol`, `k-almost-prime-membership`,
`kaprekar-split-witness`, `linear-congruence-solver`,
`linear-diophantine-class`, `liouville-parity`, `lucas-index-membership`,
`mobius-squarefree-sign`, `modular-inverse`, `multiplicative-order`,
`multiplicative-persistence`, `narcissistic-base-class`,
`palindromic-prime-base`, `polygonal-index-membership`,
`powerful-number-witness`, `prime-interval-profile`,
`primitive-pythagorean-triple`, `primitive-root-verifier`,
`quadratic-residue-witness`, `radical-square-kernel`,
`roughness-bound-profile`, `semiprime-factor-pair`, `smith-composite-class`,
`smoothness-bound-profile`, `squarefree-certificate`, `totient-density-class`,
and `triangular-index-membership`; plus
`text-grid-logic/regions-mazes/mandatory-shortest-cells`,
`text-grid-logic/regions-mazes/shortest-layer-widths`, and
`text-grid-logic/sparse-compressed-tabular/posting-skip-directory`.

## Findings

### cycle-005/family/topic-negative-fixture-literal-suffix-leak

**Severity:** blocker. **Scope:** all 40 roots and the 780-pair family gate.

The strict screen above disproves the recorded seven-dimension conjunction for
three pairs. Two are structurally identical and one exceeds the published
negative-fixture overlap ceiling. The production and focused normalizers count
numeric literal suffixes as identifiers, so their passing decision is not
valid under the explicit all-literals-erased contract.

**Required remedy:** give each affected wrong substitute a genuinely different
coherent control flow that remains plausible and is rejected by both suites;
fix the production and focused literal lexer so suffixes cannot manufacture
diversity; regenerate and rerun Docker before a fresh audit.

**Disposition:** `repair-and-reverify`. **Status:** open.

### cycle-003/family/live-source-inventory-stale

**Severity:** blocker. **Scope:** family lineage and duplicate evidence.

The audit-start reconciliation proves 43 semantic-tree mismatches and unequal
aggregates despite exact keys, configs, and file counts. The subject therefore
does not bind the live full-content inventory used for its claimed 122,600
decisions.

**Required remedy:** wait for the shared expansion families to stabilize,
freeze the live full-content inventory, rerun all comparisons, regenerate every
dependent receipt and the subject, then request a fresh audit immediately.

**Disposition:** `repair-and-reverify`. **Status:** open.

## Earlier finding dispositions

| Finding | Cycle-005 disposition |
| --- | --- |
| `cycle-001/family/public-contract-incomplete` | closed |
| `cycle-001/family/discriminator-not-task-specific` | closed |
| `cycle-001/family/oracle-coverage-not-independent` | closed |
| `cycle-001/family/diversity-controls-invalid` | closed; all three coherent controls are rejected and pass both Docker modes |
| `cycle-001/bit-morton-pair/semantic-lineage-conflict` | closed; Morton roots absent, genuine backfills present |
| `cycle-001/family/evidence-subject-incomplete` | closed; exact subject bindings reproduce |
| `cycle-001/family/metadata-provenance-incomplete` | closed |
| `cycle-001/set-symmetric-rank/bound-double-duty` | closed |
| `cycle-001/set-jaccard-ordering/operand-double-duty` | closed |
| `cycle-002/family/oracle-coverage-still-not-independent` | closed; 80 hand-derived catalog cases are present and executed |
| `cycle-002/family/diversity-controls-still-invalid` | closed |
| `cycle-002/family/source-inventory-lineage-evidence-stale` | open through the current live-inventory finding |
| `cycle-002/family/invalid-bound-contract-reference-mismatch` | closed; nine corrected cases retain current normal/sanitizer evidence |
| `cycle-003/family/seven-dimension-screen-still-non-material` | open in narrowed form: public API/oracle repair is closed, but the negative dimension still uses literal-suffix leakage |
| `cycle-003/family/constants-policy-control-incoherent` | closed |
| `cycle-003/family/live-source-inventory-stale` | open; audit-start aggregate mismatch above |
| `cycle-003/bit-next-combination/width64-overflow` | closed |
| `cycle-003/bit-submask-checksum/unbounded-valid-runtime` | closed |
| `cycle-004/family/seven-dimension-screen-still-non-material` | open through the new negative-fixture finding |
| `cycle-004/family/live-source-inventory-stale` | open through the current live-inventory finding |

## Duplicate, lineage, contamination, and composition

- The 40 candidate IDs are unique. There is no candidate-ID collision in the
  3,065 live external roots or the 26 holdouts. Rejected Morton IDs remain
  absent and both replacement backfills remain present.
- A fresh read of all 122,600 live candidate/external token comparisons finds
  no score at or above 0.94; the maximum is 0.273356
  (`bit-field-extraction` against other-expansion
  `numerical-arithmetic/overflow-scoring-combinatorial/bell-partition-count`).
  This does not cure the stale subject binding.
- The 26 official holdouts reproduce aggregate
  `sha256:72521b181cfaba63d2d859313e545ea1f503cba3988d90d49452d2dac078f0e5`.
  All 1,040 comparisons have zero exact-ID/content matches and zero score at or
  above 0.82; the maximum is 0.159259 (`bit-select-one` / `queen-attack`).
- Composition is 20 direct bit operations, three flag/set-policy operations,
  and 17 set/packed-relation operations. Every root has one visible and one
  private hand-derived targeted case, two editable whole files, a complete
  reference replacement, and one compiling wrong substitute. This is a local
  task-family audit, so tokenizer/mask, dataset split, JSONL, and train/validation
  manifests are outside the authorized scope.

## Forty-root catalog

Every root's primary objective, prompt boundary, current reference execution,
sanitizer execution, and negative rejection pass. Every root inherits the two
family blockers and remains `repair-and-reverify`.

| Root | Capability |
| --- | --- |
| `bit-swar-popcount` | SWAR population count |
| `bit-fold-parity` | XOR-fold parity |
| `bit-width-reversal` | bounded reversal |
| `bit-bounded-rotation` | bounded rotation |
| `bit-sign-extension` | sign extension |
| `bit-field-extraction` | checked extraction |
| `bit-field-insertion` | clear/deposit insertion |
| `bit-mask-compression` | PEXT-style compression |
| `bit-mask-deposition` | PDEP-style deposition |
| `bit-index-permutation` | validated destination permutation |
| `bit-carryless-product` | GF(2) product |
| `bit-gray-encoding` | Gray encoding |
| `bit-gray-decoding` | Gray decoding |
| `bit-next-combination` | equal-popcount successor |
| `bit-submask-checksum` | bounded submask enumeration |
| `bit-prefix-rank` | prefix rank |
| `bit-select-one` | ordinal set-bit selection |
| `bit-longest-run` | longest-one run |
| `bit-first-zero-run` | first zero run |
| `bit-range-toggle` | inclusive-range XOR |
| `flag-implication-closure` | implication fixed point |
| `flag-priority-conflicts` | priority conflict pruning |
| `flag-two-of-three-quorum` | bit-sliced quorum |
| `set-symmetric-rank` | symmetric-difference rank |
| `set-union-cardinality` | union/intersection counts |
| `set-intersection-select` | ranked intersection |
| `set-partition-validation` | disjoint-cover proof |
| `set-packed-exact-cover-count` | exact-cover enumeration |
| `set-packed-minimum-cover` | minimum cover |
| `set-packed-independent-weight` | weighted independent set |
| `set-packed-subset-sum` | subset-sum reachability |
| `set-zeta-transform-checksum` | subset zeta transform |
| `set-mobius-roundtrip` | subset Mobius inversion |
| `set-xor-basis-maximum` | XOR-basis maximum |
| `set-xor-basis-rank` | XOR-basis rank |
| `set-packed-transitive-closure` | Warshall closure |
| `set-packed-reachability-layers` | layered reachability |
| `set-hamming-nearest-byte` | nearest-byte selection |
| `set-jaccard-ordering` | rational Jaccard comparison |
| `set-maximal-disjoint-packing` | maximum disjoint packing |

## Next gate and non-claims

Remediation must repair the strict negative-fixture diversity and literal
lexer, wait for and freeze a stable live external inventory, regenerate the
complete family and Docker/subject evidence, and request another fresh
independent audit. This report does not establish `local_family_verified`, an
SFT release, JSONL projection, training authorization, or benchmark uplift.
