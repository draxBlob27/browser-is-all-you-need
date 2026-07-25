# Sparse, Compressed, And Tabular Expansion Curriculum

Status: implementation-owned clean-room local candidate family. This document does not create an
SFT release, authorize training, or claim benchmark uplift.

## Count-plan cell

This family supplies exactly 25 new roots for the binding 2,500-task-plan cell
`Text, grid, layout, logic, and constraint behavior / Sparse, compressed, tabular, and round-trip representations`.
It writes only below `.w8-biayn/data/aider-tasks-expansion-v1/text-grid-logic/sparse-compressed-tabular/`.
Both existing generated trees and all other expansion families are immutable inventory and semantic-screen inputs.

## Weakness and learning objective

The GLM-4.7-Flash base evidence shows unreliable first-try structured reshaping. These tasks teach
compact representation invariants, canonical ordering, exact malformed-input rejection, and explicit
round-trip reasoning without copying any official Aider task. The family deliberately excludes the
existing local sparse-matrix, table-pivot, transpose, run-length-image, and matrix-rotation contracts.

## Retained roots

| Task ID | Subtopic | Core mechanism | Private discriminator |
| --- | --- | --- | --- |
| `succinct-bit-rank-directory` | succinct index | packed bit words and rank checkpoints | rejects per-query rescanning semantics |
| `frame-reference-integer-blocks` | integer blocks | block minima and offsets | detects a global-minimum shortcut |
| `zigzag-varint-ledger` | byte compression | ZigZag plus base-128 groups | detects unsigned-cast encoding |
| `bounded-bitwidth-column` | bit packing | exact-width reservoir | detects byte-per-value storage |
| `run-end-status-column` | column compression | values plus exclusive run ends | detects length/end confusion |
| `nullable-dictionary-column` | dictionary column | sorted dictionary, ids, null bitmap | detects unstable first-seen ids |
| `front-coded-path-lexicon` | string table | prefix lengths and suffix payload | detects delimiter concatenation |
| `jagged-offset-table` | ragged table | flat payload and terminal offsets | detects fixed-width reconstruction |
| `row-dictionary-fact-table` | row compression | complete-row dictionary and row ids | detects independent cell dictionaries |
| `nullable-columnar-record-batch` | columnar layout | parallel columns plus null plane | detects dropped null positions |
| `schema-permutation-table` | tabular projection | validated name permutation | detects alphabetical sorting |
| `table-cell-delta-patch` | table versioning | sorted changed-cell triples | detects whole-row replacement |
| `full-outer-merge-table` | tabular merge | two-pointer full outer join | detects inner-join loss |
| `asof-snapshot-join` | temporal table | latest-prior monotone scan | detects nearest-future selection |
| `sparse-polynomial-canonicalizer` | sparse algebra | exponent coalescence and gap Horner | detects retained zero/duplicate terms |
| `adjacency-gap-catalog` | sparse graph | per-vertex sorted positive gaps | detects a global cross-vertex gap chain |
| `posting-skip-directory` | inverted index | posting gaps and absolute checkpoints | detects linear-from-origin query state |
| `quotient-remainder-membership` | succinct set | quotient bucket offsets and remainders | detects missing bucket boundaries |
| `block-coordinate-sparse-tensor` | sparse tensor | block coordinates and dense block payloads | detects full dense allocation |
| `symmetric-triangle-packer` | packed matrix | upper-triangle row offsets | detects diagonal-only storage |
| `binary-quadtree-leaf-stream` | hierarchical raster | preorder uniform/internal tags | detects row-run substitution |
| `boolean-interval-mask` | sparse mask | maximal half-open intervals | detects one-index-per-true-cell output |
| `last-write-sparse-overlay` | sparse mutation log | sequence-aware last-write compaction | detects first-write retention |
| `sparse-histogram-gap-stream` | sparse numeric table | positive-bin gaps plus length | detects lost trailing zero bins |
| `byte-column-bitplanes` | column transposition | eight row-aligned bit planes | detects omission of all-zero planes |

## Executable contract

The normative per-root API, invalid/duplicate/absent/empty behavior, canonical ordering, tie policy,
overflow behavior, reference representation, negative fixture, and acceptance gates are in
`docs/aider-tasks-spec/aider-text-grid-reshaping/sparse-compressed-tabular-expansion.md`.
Every root has visible and private deterministic assertions and one compiled coherent false
substitute. References must pass normal and fresh ASan/UBSan builds in the pinned network-disabled
repository C++ sanity image with equal positive discovery.

### Per-root executable coverage

The complete public behavior and concrete input/output boundary table is normative in the family
specification. The owner mirrors it in `BEHAVIOR_CASES`. `CASE_COVERAGE` assigns the following
stable executable categories: N=`normal`, E=`empty`, I=`invalid`, D=`duplicate_order`,
A=`absent_tie`, O=`overflow_tail`, M=`malformed`, and B=`boundary`. Each listed category requires a
real marked public-function invocation in the generated tests. N is visible and all other listed
categories are private. An omitted category is genuinely inapplicable to that root, not untested.

Every root also exposes `validate_<task>_encoding(request, encoded)`. This validator inspects mutable
caller-supplied emitted state without invoking the primary operation, so each `M` cell corrupts an
actual packed word, offset, end, checkpoint, coordinate, tag, interval, or plane and proves rejection
of that malformed or noncanonical representation.

| Task ID | Required categories |
| --- | --- |
| `succinct-bit-rank-directory` | N, E, I, A, O, B |
| `frame-reference-integer-blocks` | N, E, I, D, O, B |
| `zigzag-varint-ledger` | N, E, I, O, M, B |
| `bounded-bitwidth-column` | N, E, I, O, M, B |
| `run-end-status-column` | N, E, I, D, M, B |
| `nullable-dictionary-column` | N, E, I, D, A, M, B |
| `front-coded-path-lexicon` | N, E, I, D, O, M, B |
| `jagged-offset-table` | N, E, I, D, O, M, B |
| `row-dictionary-fact-table` | N, E, I, D, M, B |
| `nullable-columnar-record-batch` | N, E, I, D, A, M, B |
| `schema-permutation-table` | N, E, I, D, M, B |
| `table-cell-delta-patch` | N, E, I, D, A, O, M, B |
| `full-outer-merge-table` | N, E, I, D, A, B |
| `asof-snapshot-join` | N, E, I, D, A, B |
| `sparse-polynomial-canonicalizer` | N, E, I, D, A, O, M, B |
| `adjacency-gap-catalog` | N, E, I, D, A, M, B |
| `posting-skip-directory` | N, E, I, D, A, O, M, B |
| `quotient-remainder-membership` | N, E, I, D, A, M, B |
| `block-coordinate-sparse-tensor` | N, E, I, D, A, O, M, B |
| `symmetric-triangle-packer` | N, I, D, M, B |
| `binary-quadtree-leaf-stream` | N, I, O, M, B |
| `boolean-interval-mask` | N, E, I, D, A, O, M, B |
| `last-write-sparse-overlay` | N, E, I, D, A, O, M, B |
| `sparse-histogram-gap-stream` | N, E, I, D, A, O, M, B |
| `byte-column-bitplanes` | N, E, I, O, M, B |

This matrix is an admission contract, not documentation-only evidence. Focused tests independently
compare it with `CASE_COVERAGE`, confirm that every `BEHAVIOR_CASES` entry is published in the
instructions, and prove each marker scopes an executed call. A canonical example and a single
`width=0` rejection cannot satisfy any row with additional categories.

## Diversity and clone controls

The owner compares all 300 unordered pairs separately across the exact seven hard-rule dimensions
using the emitted docs, public API, reference, visible/private tests, and negative source. It also
materializes coherent domain/identifier-renamed, constants/policy-only, and opposite-end-selection
controls. Focused tests independently inspect every per-dimension decision and require each control
to change files, compile, pass its revised behavior tests, and be rejected by the production screen.

## Completion

Creator preflight is not completion. A read-only independent audit must bind the exact tree; any
finding routes through recorded remediation, complete owner regeneration, and a fresh read-only
audit. Exactly 25 passing roots and zero unresolved hard-gate findings may reach
`local_family_verified`. Dataset handoff remains `not_requested`.
