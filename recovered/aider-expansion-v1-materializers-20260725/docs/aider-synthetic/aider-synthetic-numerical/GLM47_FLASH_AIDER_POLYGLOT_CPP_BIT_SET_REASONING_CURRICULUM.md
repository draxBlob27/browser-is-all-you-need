# GLM-4.7-Flash Bitmask, Set, Flag, and Membership Curriculum

Status: executable clean-room expansion-v1 curriculum. This document allocates
exactly 40 new roots to the binding “Bitmask, set, flag, and membership
reasoning” cell in `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`.
It does not authorize JSONL, dataset release, training, or benchmark claims.

## Contract

Every root is a new C++17 whole-file task with one task-specific operation over
bounded 64-bit masks. The visible contract states invalid widths, absent-bit
behavior, ordering, ties, and overflow. The reference implements the advertised
mechanism without `std::bitset`, C++20 bit operations, ordered set containers,
or a table of expected answers. Visible and private tests are deterministic.
Each header exposes a task-semantic `Request` field layout with real lossless
limb decomposition rather than typedef spelling variants; public-API diversity
is measured from headers without borrowing mechanism prose. Visible and private
suites use different base vectors plus separately hand-derived, root-specific
acceptance cases. Each root owns a compiling identity/union-style false
substitute which both production suites must execute and reject.

All roots materialize only below
`.w8-biayn/data/aider-tasks-expansion-v1/numerical/bit-set-reasoning/`.
The legacy and reverify trees are immutable comparison inputs. The official 26
Aider Polyglot C++ roots are permanent holdouts.

## Selected roots

| # | Task ID | Core mechanism | Boundary or tie rule | Deliberately wrong substitute |
|---:|---|---|---|---|
| 1 | `bit-swar-popcount` | parallel SWAR population count | width 0 or >64 invalid | identity value |
| 2 | `bit-fold-parity` | XOR-fold parity reduction | only low `width` bits count | population count |
| 3 | `bit-width-reversal` | bounded mirror permutation | high bits are discarded | whole-word reversal |
| 4 | `bit-bounded-rotation` | width-local cyclic rotation | shift reduced modulo width | unbounded machine rotate |
| 5 | `bit-sign-extension` | explicit bounded sign extension | width 1..64 | zero extension |
| 6 | `bit-field-extraction` | checked offset/width extraction | field crossing bit 64 invalid | unchecked shift |
| 7 | `bit-field-insertion` | clear-and-deposit field update | source truncates to field width | OR without clearing |
| 8 | `bit-mask-compression` | software PEXT ordered compression | ascending source positions | contiguous low mask |
| 9 | `bit-mask-deposition` | software PDEP ordered deposition | excess source bits ignored | direct AND |
| 10 | `bit-index-permutation` | validated packed destination permutation | width at most 16 and every destination unique | unchecked destination scatter |
| 11 | `bit-carryless-product` | GF(2) shift-XOR polynomial product | operand width at most 32 | ordinary integer multiplication |
| 12 | `bit-gray-encoding` | binary-to-Gray transform | bounded high-bit masking | identity |
| 13 | `bit-gray-decoding` | prefix-XOR Gray decode | bounded high-bit masking | one XOR step |
| 14 | `bit-next-combination` | Gosper next equal-popcount mask | no successor returns absent | numeric increment |
| 15 | `bit-submask-checksum` | descending submask enumeration | at most 16 selected bits; includes zero exactly once | contiguous enumeration |
| 16 | `bit-prefix-rank` | rank of ones below an index | index may equal width | full popcount |
| 17 | `bit-select-one` | ordinal set-bit selection | absent ordinal is invalid | ordinal as bit index |
| 18 | `bit-longest-run` | maximal consecutive-one scan | ties choose lower start | first run only |
| 19 | `bit-first-zero-run` | first-fit zero-run allocation | ties choose lower start | highest-fit selection |
| 20 | `bit-range-toggle` | bounded inclusive range XOR | reversed range invalid | range OR |
| 21 | `flag-implication-closure` | fixed-point flag implication | cycles converge | one-pass propagation |
| 22 | `flag-priority-conflicts` | priority-ordered conflict pruning | lower index wins | keep all flags |
| 23 | `flag-two-of-three-quorum` | bit-sliced majority | masked to width | union of voters |
| 24 | `set-symmetric-rank` | ordered selection in symmetric difference | absent rank invalid | union selection |
| 25 | `set-union-cardinality` | bounded union count | outside-width bits ignored | sum counts with duplicates |
| 26 | `set-intersection-select` | ordered intersection selection | absent rank invalid | union selection |
| 27 | `set-partition-validation` | disjoint-cover proof | empty universe valid only with empty parts | union-only check |
| 28 | `set-packed-exact-cover-count` | exhaustive exact-cover enumeration | repeated coverage forbidden | any-cover count |
| 29 | `set-packed-minimum-cover` | minimum-cardinality subset cover | equal size chooses lower selector mask | greedy first cover |
| 30 | `set-packed-independent-weight` | exhaustive weighted independent set | equal weight chooses lower mask | ignore conflicts |
| 31 | `set-packed-subset-sum` | shift-OR reachability bitset | target above 63 invalid | greedy accumulation |
| 32 | `set-zeta-transform-checksum` | subset-lattice zeta transform | exactly eight nibble coefficients | prefix sum |
| 33 | `set-mobius-roundtrip` | subset-lattice Möbius inversion | signed intermediates must round-trip | arithmetic negation |
| 34 | `set-xor-basis-maximum` | GF(2) linear-basis reduction | zero vectors ignored | numeric maximum member |
| 35 | `set-xor-basis-rank` | GF(2) pivot-rank computation | duplicate vectors add no rank | nonzero count |
| 36 | `set-packed-transitive-closure` | four-row Warshall bit closure | diagonal is reflexive | one-hop adjacency |
| 37 | `set-packed-reachability-layers` | frontier/visited layered expansion | unreachable vertices excluded | transitive count only |
| 38 | `set-hamming-nearest-byte` | minimum Hamming-distance selection | tie chooses lower byte index | numeric-distance selection |
| 39 | `set-jaccard-ordering` | cross-multiplied Jaccard comparison | two empty sets compare equal | floating-point division |
| 40 | `set-maximal-disjoint-packing` | exhaustive maximum disjoint packing | cardinality tie chooses lower selector | greedy input order |

## Diversity and clone controls

The owner rereads emitted instructions, API, reference core, visible/private
oracles, and false substitute. It records all 780 unordered pairs and requires
separate decisions for: public API; owned algorithm; mutation/selection rules;
invalid/boundary behavior; reference control flow; deterministic oracle; and
topic-specific negative fixture. Three complete controls are materialized under
family `.state`: domain/identifier rename, constants/policy-only, and
opposite-end selection. Each changes files, compiles, passes its internally
consistent behavior test, and must be rejected as a clone by the production
pair evaluator.

## Completion

Creator completion requires exact owner regeneration, role/prompt checks, 780
pair decisions, cross-tree ID and semantic-lineage screens, all 1,040 official
holdout comparisons, and a network-disabled Docker sanity run. Every root and
control must have equal positive normal and fresh ASan/UBSan discovery counts;
every false substitute must compile and fail the production tests. The owner
`--verify-host` mode reruns the same per-root and per-control normal and fresh
ASan/UBSan reference checks on the host toolchain as `host_iteration`
evidence; it never substitutes for the Docker sanity run. Only a clean
fresh independent audit may set the terminal status to
`local_family_verified`.

## Docs Alignment (Remediation Docs Phase)

The model-facing `.docs` follow the official Aider Polyglot C++ conventions.
`.docs/introduction.md` is a `# <Title>` header plus a domain-motivating
narrative about bit-level systems work; it never states the contract or
mentions the evaluation harness. `.docs/instructions.md` keeps the
`# Instructions` header, the complete behavioral contract (every rule the
private tests enforce), the concrete `Public example:` line, and natural
toolchain requirements ("Do not use C++20 bit helpers, `std::bitset`, ...").
The mechanism is introduced as "Operation: <mechanism>" instead of the
scaffold-flavored "Core mechanism:" label. The generator's focused test
asserts this docs shape and rejects meta/audit vocabulary in both docs files.
