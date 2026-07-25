# Independent audit: bit and set reasoning, cycle 006

## Verdict

**Status: `not_completed`. Retained passing roots: 0 of 40.** The exact
cycle-006 subject
`sha256:7340a042f809f7fc317902da45a4745edcb9e9c2985b23288180baec2dbfcc24`
and non-state family tree
`sha256:ccf95e4ba2363e4016472453523ea3253e678bd1d0a5c858be247c000bf7af8c`
reproduce, including every bound artifact, receipt, remedy, invalidated Morton
receipt, and control tree. The cycle-005 negative-fixture defect is repaired:
an independent C++ lexer finds 40 public-header shapes, 40 combined-oracle
shapes, and 40 negative-fixture shapes, and all 780 pair conjunctions pass all
seven dimensions. The first audit operation nevertheless found the bound
external source inventory stale at audit start: ten other expansion roots had
changed semantic-tree hashes. This is a family hard gate, so all 40 roots
remain `repair-and-reverify`; this exact subject is not
`local_family_verified`.

## Behavior contract used for this audit

Each root must be a prompt-solvable C++17 whole-file task with two declared
editable files. Its reference must implement the published bit/set mechanism,
including invalid, empty, boundary, ordering, and tie behavior. Its visible and
private deterministic cases must exercise the declared request/result contract,
and one coherent compiling wrong substitute must be rejected by both suites.
Across all 780 unordered root pairs, the public API, owned algorithm, selection
rules, invalid/boundary rules, reference control flow, deterministic oracle,
and wrong substitute must each be structurally distinct after comments,
strings, character and complete numeric literals (including every suffix), and
all non-keyword identifiers are erased. Exact legacy, reverify,
other-expansion, and 26 official-holdout inputs must be bound to the audit
subject.

## Audit-start source-inventory reconciliation

This was the first audit operation. Recorded and live counts matched exactly:
3,065 external roots (731 legacy, 709 reverify, 1,625 other expansion), 40,657
semantic files, and 122,600 candidate/external comparisons. There were zero
live-only or recorded-only keys. Task IDs, config hashes, and semantic file
counts matched. The recorded full-content aggregate was
`sha256:5ae1d73e9c5cf382b620db848bde03809fdff02c15e71f47acc916d3f2dda5ae`;
the independently computed live aggregate at audit start was
`sha256:18578021c075177590ba46fef6db05047f0efabc410f782eac01b6e2a3b00a29`.

The ten audit-start semantic-tree mismatches were all under
`state-concurrency/producer-consumer-behavior-structures/`:

- `abortable-batch-handoff`
- `cascading-stage-closure`
- `epoch-sealed-inbox`
- `half-close-duplex-handoff`
- `orphan-reclaim-handoff`
- `phased-drain-controller`
- `poison-free-stop-barrier`
- `producer-lease-shutdown`
- `reopen-generation-mailbox`
- `terminal-error-broadcast`

Other expansion families continued changing after that frozen audit-start
comparison. Later reads therefore cannot cure the subject's stale binding.

## Subject, structure, prompt, and executable evidence

- Canonical recomputation of the subject JSON matches the claimed subject
  hash. The 14 scalar artifact bindings, 40 retained receipt hashes, 80 remedy
  hashes, two invalidated Morton receipt hashes, and three control-tree hashes
  all match current bytes. The family has exactly 40 selected unique IDs and
  520 non-state files, 13 per root.
- All 40 per-root tree hashes reproduce. All 40 prompts independently rebuild
  to their recorded hashes and editable-file order. Prompt lengths are
  3,381--5,309 characters. No CMake, provenance, reference, hidden-test,
  negative-fixture, `.meta`, or `.state` material appears in a prompt.
- The targeted-case catalog contains exactly 40 records and 80 hand-derived
  visible/private cases. Every recorded request and expected result triple
  occurs in its designated emitted test. Config roles, clean-room provenance,
  whole-file boundaries, and `dataset_handoff: not_requested` are consistent
  for all 40 roots.
- The current receipt binds the owner, curriculum, specification, focused
  test, subject tree, mounted tree, and all test hashes. It records 40 normal
  and 40 fresh ASan/UBSan task records, exactly two discovered CTests per root,
  and nonzero visible/private negative exits in both modes. No record is
  missing or stale.
- The designated network-disabled image is
  `sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`.
  The recorded compiler is `/usr/local/bin/c++`, GCC 13.4.0, digest
  `sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`;
  CMake is 3.25.1.
- All three clone controls are coherent, materially changed, and rejected by
  the production screen. The Docker receipt contains six passing control-mode
  records (normal and sanitizer for rename-only, constants-policy-only, and
  opposite-end-selection), each with two discovered tests and both negative
  executables rejected.
- The independent focused invocation reports `6 passed`.

## Independent emitted-structure screen

The independent lexer erases C++ comments, raw/ordinary strings, character
literals, and complete binary, hexadecimal, and decimal numeric literals with
their `U`/`L`/other suffixes. It maps every non-C++-keyword identifier,
including `std` and fixed-width typedef spellings, to one neutral identifier
token. Contract prose is not read. Position-aware trigram sets and the
published per-dimension ceilings are then applied to emitted headers,
reference cores, visible/private tests, and negative fixtures.

| Dimension | Strict shapes | Equal pairs | Failing pair decisions | Maximum overlap |
| --- | ---: | ---: | ---: | ---: |
| public API | 40 | 0 | 0 | 0.742406 |
| owned state or algorithm | 40 | 0 | 0 | 0.566038 |
| mutation/selection rules | 40 | 0 | 0 | 0.366352 |
| invalid/boundary behavior | 40 | 0 | 0 | 0.351880 |
| reference control flow | 40 | 0 | 0 | 0.566038 |
| deterministic visible/private oracle | 40 | 0 | 0 | 0.574545 |
| topic negative fixture | 40 | 0 | 0 | 0.939227 |

All 5,460 dimension decisions and all 780 seven-dimension conjunctions pass.
In particular, the three cycle-005 failing negative pairs now pass without
literal-suffix or identifier leakage.

## Finding

### cycle-003/family/live-source-inventory-stale

**Severity:** blocker. **Scope:** family lineage and duplicate evidence.

The exact audit-start reconciliation proves ten semantic-tree mismatches and
unequal full-content aggregates. The subject therefore does not bind the live
external corpus used for its claimed 122,600 lineage comparisons. The fact
that other families continued mutating during this audit reinforces that a
later unbound comparison is not admissible evidence for this subject.

**Required remedy:** wait until shared expansion materialization is stable,
freeze the exact live full-content inventory, rerun the 122,600 comparisons,
regenerate every dependent screen, receipt, and subject, and request an
immediate fresh independent audit.

**Disposition:** `repair-and-reverify`. **Status:** open.

## Earlier finding dispositions

| Finding | Cycle-006 disposition |
| --- | --- |
| `cycle-001/family/public-contract-incomplete` | closed |
| `cycle-001/family/discriminator-not-task-specific` | closed |
| `cycle-001/family/oracle-coverage-not-independent` | closed |
| `cycle-001/family/diversity-controls-invalid` | closed |
| `cycle-001/bit-morton-pair/semantic-lineage-conflict` | closed; Morton roots absent and genuine backfills present |
| `cycle-001/family/evidence-subject-incomplete` | closed |
| `cycle-001/family/metadata-provenance-incomplete` | closed |
| `cycle-001/set-symmetric-rank/bound-double-duty` | closed |
| `cycle-001/set-jaccard-ordering/operand-double-duty` | closed |
| `cycle-002/family/oracle-coverage-still-not-independent` | closed; all 80 hand-derived cases are present and executed |
| `cycle-002/family/diversity-controls-still-invalid` | closed |
| `cycle-002/family/source-inventory-lineage-evidence-stale` | open through the current live-inventory finding |
| `cycle-002/family/invalid-bound-contract-reference-mismatch` | closed |
| `cycle-003/family/seven-dimension-screen-still-non-material` | closed by the independent strict 40-shape screen |
| `cycle-003/family/constants-policy-control-incoherent` | closed |
| `cycle-003/family/live-source-inventory-stale` | open |
| `cycle-003/bit-next-combination/width64-overflow` | closed |
| `cycle-003/bit-submask-checksum/unbounded-valid-runtime` | closed |
| `cycle-004/family/seven-dimension-screen-still-non-material` | closed |
| `cycle-004/family/live-source-inventory-stale` | open through the current live-inventory finding |
| `cycle-005/family/topic-negative-fixture-literal-suffix-leak` | closed; 40 strict negative shapes, zero equal/failing pairs |

## Duplicate, contamination, and composition report

- Candidate IDs are unique, with no collision against the 3,065 external
  roots or 26 official holdouts. Rejected `bit-morton-interleave` and
  `bit-morton-deinterleave` remain absent; `bit-index-permutation` and
  `bit-carryless-product` remain present as replacement backfills.
- A diagnostic fresh read of all 122,600 candidate/external token comparisons
  found no overlap at or above 0.94; the maximum was 0.271698. This does not
  close the stale subject binding.
- The 26 official holdouts reproduce aggregate
  `sha256:72521b181cfaba63d2d859313e545ea1f503cba3988d90d49452d2dac078f0e5`.
  All 1,040 comparisons have zero exact-ID/content matches and no similarity
  at or above 0.82; the independent maximum is 0.162037.
- Composition remains 20 direct bit operations, three flag/set-policy
  operations, and 17 set/packed-relation operations. Each root has two
  editable files, complete private replacements, visible/private deterministic
  tests, and one compiling wrong substitute. Tokenizer/mask evidence, JSONL,
  split selection, release packaging, and training are outside this local
  family audit.

## Forty-root catalog

Every root passes its task-local prompt, structure, targeted-case, normal,
sanitizer, and negative gates. Every root inherits the family inventory blocker
and remains `repair-and-reverify`.

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

The creator must freeze a stable live inventory, regenerate the dependent
lineage, Docker, per-root receipt, and subject evidence, and request a fresh
audit. This report does not establish `local_family_verified`, an SFT release,
JSONL projection, training authorization, or benchmark uplift.
