# Independent audit: bit and set reasoning, cycle 002

## Verdict

**Status: `not_completed`. Retained passing roots: 0 of 40.** The exact
cycle-002 subject is reproducible and its current task tree has strong recorded
Docker execution evidence, but three cycle-001 hard-gate findings are not
actually remedied. A new reference/contract mismatch affects nine roots. All
40 roots therefore remain `repair-and-reverify`; none may be described as
`local_family_verified`.

Audit subject:
`sha256:3ba3d98d08701f07ae538eeba115e0d60def605ebe56167798877243a2e2aba1`.
I independently recomputed its canonical JSON hash and the non-state tree hash:

- task tree:
  `sha256:18a8a9948610750d269081abcb98217a9075fd321068cb74742b42bfcbe40ce4`
- 40 roots and 520 non-state files, exactly 13 files per root
- all scalar, 40 retained per-root receipt, 80 remedy-file, two stale-receipt,
  and three control-tree bindings match the files named by the subject
- prompt hashes independently reproduce for all 40 roots; prompt lengths are
  2,082--2,368 characters and no CMake, provenance, reference, hidden-test,
  negative-fixture, or tests-manifest path occurs in a prompt
- the pinned image independently resolves to
  `sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`;
  the network-disabled image reports `/usr/local/bin/c++`, GCC 13.4.0,
  compiler hash
  `sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
  and CMake 3.25.1, matching the receipt
- the receipt records 40 normal and 40 fresh sanitizer results with two
  discovered CTests per root; both visible and hidden negative executables
  return nonzero in both modes; all three controls have the same recorded
  normal/sanitizer execution shape

This evidence proves that the recorded examples and discriminators execute in
the recorded environment. It does not compensate for incomplete assertions,
an invalid diversity proof, or stale corpus-screen inputs.

## Behavior contract used for the audit

Each root must expose a complete C++17 whole-file contract and a correct
reference for normal, invalid, empty, duplicate, absent, ordering, tie,
overflow, and packed-field behavior that applies to it. Every material rule
must have an independently checkable deterministic assertion. The 40 counted
roots must differ materially in each of the seven required dimensions after
task/domain identifiers, comments, strings, and literals are removed. The
three adversarial controls must be genuine, internally coherent, buildable
rename-only, constants/policy-only, and opposite-end clones. Duplicate and
holdout screening must bind the exact compared corpus.

## Findings

### cycle-002/family/oracle-coverage-still-not-independent

**Severity:** blocker. **Scope:** all 40 roots. **Disposition:**
`repair-and-reverify`. **Status:** open.

Every visible test invokes its operation on exactly two vectors. Every hidden
test invokes the same two vectors in the opposite order; it does not add an
independent normal vector. Seventeen hidden tests add no further assertion,
21 add one generic invalid call, and two add two invalid calls. After task
identifiers and numeric literals are removed, all 40 visible tests are one
identical assertion template and the hidden tests have only three structural
variants. The owner and the expected literals are emitted from the same
`_oracle`/`INPUTS` source.

Consequently the suites do not establish each root's published empty,
duplicate, absent, upper-bound, ordering, tie, overflow, ignored-field, or
packed-lane rules. The Docker receipt proves only that these duplicated
examples pass and each chosen negative fails. This leaves
`cycle-001/family/oracle-coverage-not-independent` open. Repair requires
root-specific visible/private properties and boundary/tie/invalid cases whose
expected outcomes are independently derived, followed by full regeneration
and fresh Docker evidence.

### cycle-002/family/diversity-controls-still-invalid

**Severity:** blocker. **Scope:** all 40 roots and all 780 pairs.
**Disposition:** `repair-and-reverify`. **Status:** open.

After independently removing each task namespace/function/slug, comments,
strings, and literals, all 40 emitted headers collapse to one identical
`Result` plus three-argument function shape: one public-API variant and 780
equal public-API pairs. The production screen reports every public-API pair as
distinct only because `_features` concatenates the mechanism phrase to the
header. The focused test repeats the same defect by concatenating the entire
contract. This does not independently prove the actual public-API dimension.
Likewise, all visible oracle files collapse to one assertion structure and the
hidden files to only three structures; contract vocabulary manufactures their
reported deterministic-oracle differences.

Two required controls are not genuine coherent mutations:

- `constants-policy-only` changes two test literals and appends "uses only
  widths four and six", but leaves the original 1..64 contract, API, and
  reference acceptance policy intact.
- `opposite-end-selection` says both "Equal lengths choose the lower start"
  and "Every equal-length run tie chooses the larger start index" in the same
  public prompt. Its reference and tests implement the latter, so the control
  builds but is not internally consistent.

The family screen also writes `coherent: true` and
`production_rejected: true` as constants. Runtime evidence shows each control
passes its own tests and rejects its inherited negative; it does not make the
contradictory prompt coherent. This leaves
`cycle-001/family/diversity-controls-invalid` open.

### cycle-002/family/source-inventory-lineage-evidence-stale

**Severity:** blocker. **Scope:** family evidence. **Disposition:**
`repair-and-reverify`. **Status:** open.

The subject now binds the source-inventory and lineage-screen files, but those
files do not describe one exact current comparison corpus:

- `source-inventory.json` has 3,065 records, while its declared counts sum to
  3,105 because `expansion_before_count` includes the 40 candidate roots that
  its records intentionally exclude.
- Independent reconciliation against the live trees finds 16 recorded config
  bindings missing or changed.
- `lineage-screen.json` claims 123,200 comparisons, or 3,080 external roots
  times 40 candidates, while the current independently discovered external
  inventory has 3,065 roots.
- The source inventory binds only config files, not the docs/API/reference/test
  bytes used by the semantic comparison.

For audit context, the current external corpus contains 3,065 roots and 40,137
files with independently observed full-content aggregate
`sha256:77d5af858c771111c3bd23340967177fe8dc2e39a941d13901ae865f632811f9`.
An independent identifier-normalized token screen found no candidate overlap
at or above 0.8 (maximum 0.315316), and no current exact candidate-ID
collision. Those observations do not repair the stale owner receipt. This
leaves `cycle-001/family/evidence-subject-incomplete` open; regeneration must
freeze full semantic-input digests and reconcile the exact record and
comparison counts.

### cycle-002/family/invalid-bound-contract-reference-mismatch

**Severity:** blocker. **Scope:** nine roots. **Disposition:**
`repair-and-reverify`. **Status:** open.

The public contracts say `bound <= N` and the common failure rule says invalid
requests return `{false,0,0}`, but these references silently clamp excessive
bounds instead of rejecting them:

- `set-packed-exact-cover-count`, `set-packed-minimum-cover`,
  `set-packed-independent-weight`, `set-packed-transitive-closure`, and
  `set-packed-reachability-layers` clamp to four;
- `set-xor-basis-maximum`, `set-xor-basis-rank`,
  `set-hamming-nearest-byte`, and `set-maximal-disjoint-packing` clamp to eight.

The closure and reachability references also fail to mask each nibble row to
the declared `n` vertices, so out-of-domain destination bits can leak into the
returned packed closure or reachable mask. The current tests never exercise
these counterexamples. Repair the reference and assertions, not the prose
alone.

## Cycle-001 finding dispositions

| Cycle-001 finding | Fresh-audit disposition |
| --- | --- |
| `cycle-001/family/public-contract-incomplete` | closed: every root now has an explicit packed/input/output contract and public example |
| `cycle-001/family/discriminator-not-task-specific` | closed: 40 distinct task-specific compiling negatives are executed by visible and hidden suites in both modes |
| `cycle-001/family/oracle-coverage-not-independent` | open; superseded in detail by `cycle-002/family/oracle-coverage-still-not-independent` |
| `cycle-001/family/diversity-controls-invalid` | open; superseded in detail by `cycle-002/family/diversity-controls-still-invalid` |
| `cycle-001/bit-morton-pair/semantic-lineage-conflict` | closed as a replacement action: both Morton roots are absent and `bit-index-permutation` / `bit-carryless-product` are present; the new roots still share the family blockers |
| `cycle-001/family/evidence-subject-incomplete` | open; superseded in detail by `cycle-002/family/source-inventory-lineage-evidence-stale` |
| `cycle-001/family/metadata-provenance-incomplete` | closed: all 40 configs/provenance records bind CC0-1.0, clean-room origin, inventory ID, lineage, selected prompts, and private roles |
| `cycle-001/set-symmetric-rank/bound-double-duty` | closed: width and rank are separate packed fields and the reference follows that contract |
| `cycle-001/set-jaccard-ordering/operand-double-duty` | closed: the second set and packed rational threshold are separate operands and the three result codes are public |

## Duplicate, lineage, and contamination report

- Selected IDs: 40 unique; current exact collisions against legacy, reverify,
  and other expansion roots: zero.
- Replaced IDs: `bit-morton-interleave` and `bit-morton-deinterleave` are
  absent. Backfills `bit-index-permutation` and `bit-carryless-product` are
  present with explicit replacement lineage.
- Current independent semantic scan: no overlap at or above 0.8 across 3,065
  external roots; strongest token overlap 0.315316. This is diagnostic because
  the owner ledger is stale as described above.
- Official holdouts: all 26 required roots are present at upstream revision
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`; their 304-file aggregate is
  `sha256:4bcc1a16ea481af659750309767d9af113e6588abc05342afc062f7d1876a5d5`.
  No exact ID/content match or semantic conflict was confirmed. The recorded
  1,040 comparisons are consistent with 40 by 26.

## Corpus composition and root catalog

The family has 20 bit primitives, three flag operations, and 17 set or
combinatorial operations. All are synthetic clean-room C++17 single-turn
whole-file tasks with two editable files, one shared API shape, two duplicated
normal vectors, and one task-specific negative. Tokenizer/mask and split
evidence are dataset-release gates and are neither required nor claimed here.

Every row below has disposition `repair-and-reverify`, remediation route
`repair-in-place`, and `primary_core_objective: not_achieved` because the
family-level oracle and diversity gates fail.

| Root | Capability | Additional root-specific blocker |
| --- | --- | --- |
| `bit-swar-popcount` | SWAR count | -- |
| `bit-fold-parity` | XOR parity | -- |
| `bit-width-reversal` | bounded reversal | -- |
| `bit-bounded-rotation` | bounded rotation | -- |
| `bit-sign-extension` | sign extension | -- |
| `bit-field-extraction` | checked extraction | -- |
| `bit-field-insertion` | clear/deposit insertion | -- |
| `bit-mask-compression` | PEXT compression | -- |
| `bit-mask-deposition` | PDEP deposition | -- |
| `bit-index-permutation` | validated destination permutation | -- |
| `bit-carryless-product` | GF(2) product | -- |
| `bit-gray-encoding` | Gray encoding | -- |
| `bit-gray-decoding` | Gray decoding | -- |
| `bit-next-combination` | equal-popcount successor | -- |
| `bit-submask-checksum` | submask enumeration | -- |
| `bit-prefix-rank` | prefix rank | -- |
| `bit-select-one` | ordinal set-bit select | -- |
| `bit-longest-run` | longest-one run | -- |
| `bit-first-zero-run` | first zero-run | -- |
| `bit-range-toggle` | inclusive range XOR | -- |
| `flag-implication-closure` | implication closure | -- |
| `flag-priority-conflicts` | priority conflict pruning | -- |
| `flag-two-of-three-quorum` | bit-sliced quorum | -- |
| `set-symmetric-rank` | symmetric-difference rank | -- |
| `set-union-cardinality` | union/intersection count | -- |
| `set-intersection-select` | ranked intersection | -- |
| `set-partition-validation` | disjoint-cover proof | -- |
| `set-packed-exact-cover-count` | exact-cover enumeration | excessive bound is clamped |
| `set-packed-minimum-cover` | minimum cover | excessive bound is clamped |
| `set-packed-independent-weight` | weighted independent set | excessive bound is clamped |
| `set-packed-subset-sum` | subset-sum bitset | -- |
| `set-zeta-transform-checksum` | subset zeta transform | -- |
| `set-mobius-roundtrip` | subset Mobius inversion | -- |
| `set-xor-basis-maximum` | XOR basis maximum | excessive bound is clamped |
| `set-xor-basis-rank` | XOR basis rank | excessive bound is clamped |
| `set-packed-transitive-closure` | Warshall closure | excessive bound clamped; rows not masked to n |
| `set-packed-reachability-layers` | layered reachability | excessive bound clamped; rows not masked to n |
| `set-hamming-nearest-byte` | nearest-byte select | excessive bound is clamped |
| `set-jaccard-ordering` | rational Jaccard comparison | -- |
| `set-maximal-disjoint-packing` | disjoint packing | excessive bound is clamped |

## Next gate

Preserve this report and cycle 001 unchanged. Route the four cycle-002 finding
IDs through `aider-task-family-remediation`; add genuinely independent
root-specific property/boundary assertions, repair the nine references,
implement three coherent clone controls, make the public-API dimension inspect
the emitted API rather than mechanism prose, and freeze the exact full-content
comparison inventory. Regenerate all 40 roots, rerun focused tests and the
complete network-disabled normal/sanitizer/negative/control Docker pass, create
a new exact subject, and request another fresh independent audit.

This audit authorizes no SFT release, JSONL projection, training, or benchmark
uplift claim.
