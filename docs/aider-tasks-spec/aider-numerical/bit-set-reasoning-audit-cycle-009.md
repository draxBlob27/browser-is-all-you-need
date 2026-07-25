# Independent audit: bit and set reasoning, cycle 009

## Verdict

**Status: `local_family_verified`. Retained passing roots: 40 of 40.** The
exact cycle-009 subject
`sha256:105f18956d97a4c8cd11a6511c373c8804c2f9451c4efb90bbe72d4520223939`
and non-state family tree
`sha256:ccf95e4ba2363e4016472453523ea3253e678bd1d0a5c858be247c000bf7af8c`
reproduce. The audit-start source inventory is exact, all task-local and family
gates pass, all earlier findings are closed, and there are zero retained
review, repair, conflict, or contamination dispositions.

## Behavior contract

Each retained root is a prompt-solvable C++17 whole-file task with exactly two
declared editable files. Its public contract defines the bit/set operation,
invalid and empty behavior, bounds, ordering, ties, and overflow. The private
reference must implement that contract, visible and private deterministic tests
must execute it, and a coherent compiling wrong substitute must be rejected by
both suites. Across all 780 unordered pairs, each of the seven creator-skill
dimensions must remain structurally different after C++ comments, raw and
ordinary strings, character literals, complete numeric literals and suffixes,
and every non-language identifier are erased. Legacy, reverify,
other-expansion, and 26 official holdout inputs are comparison-only evidence.

## Audit-start source inventory

This was the first audit operation. The live and recorded inventories match
byte-for-byte at the record level:

- 3,065 external roots: 731 legacy, 709 reverify, and 1,625 other expansion;
- 40,657 semantic files;
- no live-only, recorded-only, changed-config, changed-file-count, or
  changed-semantic-tree records;
- aggregate
  `sha256:f9bf217a39ac909a0f7f4b6251c9f5346350d0f3df3f5ad53091c28fa0ba0294`;
- exactly 122,600 candidate/external comparisons bound to that inventory.

This closes the recurrent live-source-inventory blocker for the exact current
subject.

## Subject, prompt, and executable evidence

- Canonical subject recomputation matches the claimed hash. All 14 scalar
  bindings, 40 current receipt hashes, 80 remedy hashes, two invalidated Morton
  receipt hashes, and three control-tree hashes match current bytes.
- The family contains exactly 40 selected unique roots and 520 non-state files,
  13 per root. Every root tree hash reproduces.
- All 40 prompts independently rebuild to their recorded hashes and editable
  order. Lengths are 3,381--5,309 characters. No CMake, provenance, reference,
  hidden-test, negative-fixture, `.meta`, or `.state` content leaks into a
  prompt.
- All config roles and clean-room provenance records are valid; every root says
  `dataset_handoff: not_requested`.
- The targeted-case catalog has 40 records and 80 distinct hand-derived
  visible/private cases. Every request and expected triple is present in its
  designated emitted test, and the focused suite cross-checks every expected
  result. The independent focused run reports `6 passed`.
- The current Docker receipt binds the exact tree, mounted tree, owner,
  curriculum, specification, focused test, references, tests, and negatives.
  It records 40 normal and 40 fresh ASan/UBSan results, exactly two discovered
  CTests per root, and nonzero visible/private negative exits in both modes.
- The network-disabled image is
  `sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
  The compiler is `/usr/local/bin/c++`, GCC 13.4.0, digest
  `sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`;
  CMake is 3.25.1.
- Rename-only, constants-policy-only, and opposite-end controls are coherent,
  materially changed, rejected by the production screen, and have six passing
  Docker mode records. Each discovers two tests and rejects both negatives.

## Independent strict emitted-structure screen

The independent lexer retains only C++ language keywords, operators, and
punctuation after removing comments and all literal/identifier information.
It uses position-aware trigrams and the published per-dimension ceilings.

| Dimension | Strict shapes | Equal pairs | Failing decisions | Maximum overlap |
| --- | ---: | ---: | ---: | ---: |
| public API | 40 | 0 | 0 | 0.746479 |
| owned state or algorithm | 40 | 0 | 0 | 0.561702 |
| mutation/selection rules | 40 | 0 | 0 | 0.350929 |
| invalid/boundary behavior | 40 | 0 | 0 | 0.350929 |
| reference control flow | 40 | 0 | 0 | 0.561702 |
| deterministic visible/private oracle | 40 | 0 | 0 | 0.267016 |
| topic negative fixture | 40 | 0 | 0 | 0.942308 |

All 5,460 per-dimension decisions and all 780 seven-dimension conjunctions
pass. In particular, no result depends on task names, namespace/function names,
fixed-width typedef spelling, contract prose, or numeric-literal suffixes.

## Findings and dispositions

There are no new findings and no open findings. The recurrent inventory
findings from cycles 002--004 are closed by the exact audit-start inventory.
All other earlier findings remain closed:

| Finding group | Cycle-007 disposition |
| --- | --- |
| cycle-001 public contract, discriminator, oracle, controls, evidence, metadata, and overloaded-field findings | closed |
| cycle-001 Morton semantic-lineage conflict | closed; Morton roots absent and genuine backfills present |
| cycle-002 independent cases, controls, inventory, and bound/reference findings | closed |
| cycle-003 material diversity, control coherence, inventory, width-64 overflow, and bounded-runtime findings | closed |
| cycle-004 material diversity and inventory findings | closed |
| cycle-005 negative-fixture literal-suffix finding | closed |

Every retained root therefore has terminal audit disposition `train` in the
audit skill's row vocabulary and `verified` in the local-family vocabulary.
No rejected or replaced root is counted.

## Duplicate, contamination, and composition report

- Selected IDs are unique and do not collide with any of the 3,065 bound
  external roots. `bit-morton-interleave` and `bit-morton-deinterleave` are
  absent; `bit-index-permutation` and `bit-carryless-product` are present as
  genuine replacement backfills.
- Fresh recomputation of all 122,600 candidate/external comparisons finds zero
  similarities at or above 0.94; the maximum is 0.273356.
- The 26 official holdouts reproduce aggregate
  `sha256:72521b181cfaba63d2d859313e545ea1f503cba3988d90d49452d2dac078f0e5`.
  All 1,040 comparisons have zero ID/content matches and zero similarity at or
  above 0.82; the maximum is 0.159259.
- Composition is 20 direct bit operations, three flag/set-policy operations,
  and 17 set/packed-relation operations. Every root has two editable files,
  complete private replacements, visible/private tests, and one compiling
  task-specific wrong substitute.

## Retained root catalog

`bit-swar-popcount`, `bit-fold-parity`, `bit-width-reversal`,
`bit-bounded-rotation`, `bit-sign-extension`, `bit-field-extraction`,
`bit-field-insertion`, `bit-mask-compression`, `bit-mask-deposition`,
`bit-index-permutation`, `bit-carryless-product`, `bit-gray-encoding`,
`bit-gray-decoding`, `bit-next-combination`, `bit-submask-checksum`,
`bit-prefix-rank`, `bit-select-one`, `bit-longest-run`, `bit-first-zero-run`,
`bit-range-toggle`, `flag-implication-closure`, `flag-priority-conflicts`,
`flag-two-of-three-quorum`, `set-symmetric-rank`, `set-union-cardinality`,
`set-intersection-select`, `set-partition-validation`,
`set-packed-exact-cover-count`, `set-packed-minimum-cover`,
`set-packed-independent-weight`, `set-packed-subset-sum`,
`set-zeta-transform-checksum`, `set-mobius-roundtrip`,
`set-xor-basis-maximum`, `set-xor-basis-rank`,
`set-packed-transitive-closure`, `set-packed-reachability-layers`,
`set-hamming-nearest-byte`, `set-jaccard-ordering`, and
`set-maximal-disjoint-packing` all pass.

## Scope limit

The strongest truthful status is `local_family_verified`. This audit does not
authorize JSONL projection, an SFT release, split selection, training, or a
benchmark-uplift claim.
