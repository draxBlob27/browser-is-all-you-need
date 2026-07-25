# Coordinate Transformations Expansion: Independent Audit Cycle 02

Audit date: 2026-07-22
Audit subject: `.w8-biayn/data/aider-tasks-expansion-v1/text-grid/coordinate-transformations/`
Decision: **`not_completed`**

## Result first

The exact post-remediation subject contains 25 candidate roots and 325
non-state task files. Its independently recomputed owner-policy tree hash is
`sha256:20263dbc7b439dfb944721fd4e691a97b9b04890af35a0a432c04b9258d97c04`,
which matches the manifest, cycle-02 creator receipt, Docker receipt, and the
audit subject supplied for this cycle.

The four cycle-01 correctness findings are closed. The named Morton root from
CT-AUD-002 is absent, and its `coord-hex-ring-address` replacement is a valid,
semantically new backfill. The exact quarter-pose, voxel `INT_MIN`, invalid
cubemap-enum, and polyline `2^63` regressions all pass independent raw reference
execution under the pinned ASan/UBSan image.

The family still cannot be retained as 25 verified roots. One new hard-gate
finding is open, and the final inventory freeze check reopens CT-AUD-001:

- **CT-AUD-001 (reopened):** the candidate subject is unchanged, but the live
  expansion comparison inventory replaced `rational-weighted-median` with
  `rational-amortization-schedule` after creator preflight. Record count remains
  1,640, but the live all-ID hash is now
  `sha256:5f758b84c7f56c0b00e134f47d6810d19fe0d25551167214068a528a6ee9a7e3`
  instead of the frozen
  `sha256:bbe797ba5c66a7cc72c062c26b9b6d5385d95faca3f4b783f181378759f1956f`.

- **CT-AUD-007:** `coord-quadtree-path` is semantically equivalent to the
  already inventoried `basecv-morton-interleave-radix` task. Both encode and
  decode the same top-down paired x/y bits as base-four quadrant digits. At
  size 256 they agree for all 65,536 coordinate pairs after only the fixed
  digit relabel `0->0, 1->2, 2->1, 3->3`. Dynamic width and compass labels do
  not create a different primary mechanism.

Cycle 02 therefore assigns 24 roots `retain-pending-regeneration` and one root
`replace-and-reverify`. No root is terminally admitted while the exact 25-root
family is blocked. The next gate is a stable live inventory, generator-owned
replacement of `coord-quadtree-path` with a semantically new root, strengthened
cross-alias clone controls, complete regeneration, creator preflight, and a
fresh independent audit of the new exact tree.

## Frozen subject and evidence

| Evidence | SHA-256 or value |
| --- | --- |
| Candidate tree, excluding `.state` by owner policy | `sha256:20263dbc7b439dfb944721fd4e691a97b9b04890af35a0a432c04b9258d97c04` |
| Non-state roots / files | `25 / 325` |
| Owner | `sha256:c1a529f581b66a5f88bb05bc07388858344dc648ce62a0cac2956d23df7ebf5d` |
| Curriculum | `sha256:832074bc9fa30a8ac723cea93e1ed20bcd14275a28e24aae6c45985d31ea88e1` |
| Family specification | `sha256:50698fe624ccd90cf6c019e91f23a61a352c9aaf9331550a586526878290d9a2` |
| Focused tests | `sha256:094df37c7646d4f53451e0e3ebb23b9d4fd2ec642d8a4452406b6a68837d4fc7` |
| Manifest bytes | `sha256:8a39b9c1eb9ba19158f750348e62680155721fd97a35725bd73277ffe7f703f4` |
| Frozen source inventory bytes | `sha256:24b4c3297448e2e12952965b46f615613a51c2197aa59867e8df2a1e09222113` |
| Diversity screen bytes | `sha256:bab8349cd49a22f8c9955af1ad8a07ba3faab8c22aba5009691b316a8ee87780` |
| Contamination screen bytes | `sha256:378f2fb3bb34706e5f8016a207b0613fba4294e11a62f5ecde335a2f4be00959` |
| Adversarial-control manifest bytes | `sha256:3026d35e39afd6d3bc11cee38a5c9ca88d97f842b375d4bce02fd007284b505c` |
| Docker-sanity receipt bytes | `sha256:14a1de2f50a1ead04b075310e5ee56801f68bc941bc73926f7e62fb802e365b3` |
| Creator-preflight receipt bytes | `sha256:676c071e81b14ad4d5e0cecc91dab704b14114a7cc9fffd9d966af2a5884bdb3` |
| Cycle-02 creator receipt bytes | `sha256:6a802ee0a8d2bc7ef8e33b37492bed9968cf56e80a9af41450020cdd4caed17e` |
| Root-status bytes | `sha256:5207db05deefb39ad2e9ad6f8b189ee4b1ea4984b2954aeffed0e7433f037b61` |
| Immutable cycle-01 report | `sha256:e4b83295702acb04e19e49001146917a8fef052f4e47b36e79e79dc1773c15b9` |

The six remedy-record hashes match the cycle-02 creator receipt:

| Finding | Remedy record SHA-256 |
| --- | --- |
| CT-AUD-001 | `sha256:2453704594ba133ab19063585ffbb36aab0904e99ca1414b81c611f570f9bee6` |
| CT-AUD-002 | `sha256:b771d61978edb86474c40f55d722415ea44a428c1938a6525628fd62c067d601` |
| CT-AUD-003 | `sha256:468abd5f220e25b9ab1a51c58257403e081d3a208811ec6796f6ae484bf09cf0` |
| CT-AUD-004 | `sha256:dc69af2d1e73b2bed59370310018879ed2cb252773c48698aeaeba896aec9d74` |
| CT-AUD-005 | `sha256:eca400b50669442735b8365ad1064b6970d200898ce765306237b6a6e8971b48` |
| CT-AUD-006 | `sha256:361ce5dddfea88c2661738a49efd5f5aa7e0b18ac3b35bcd184cb13dc1c3e8eb` |

The runtime receipt binds image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
the identical image ID, network policy `none`, GCC 13.4.0 at
`/usr/local/bin/g++` with compiler hash
`sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
and CMake 3.25.1. Its live and mounted hashes both match the audit subject. It
is repository Docker-sanity evidence, not a locked family-specific oracle.

## Behavior contract used for audit

| Field | Contract |
| --- | --- |
| Task | Implement each declared C++17 coordinate transformation exactly. |
| Inputs | Only typed public API values; deterministic, offline, standard library only. |
| Output | Complete replacements for the declared header and source, with no other files or prose. |
| Invariants | Exact public API, failure-atomic invalid return, checked arithmetic, documented orientation/order/tie policy, and no private-role leakage. |
| Failure behavior | Invalid or unrepresentable inputs return the documented empty/false optional result without partial output or undefined behavior. |
| Resource limits | No network or third-party dependency; finite public domains where stated. No SFT token/context limit is authorized for this local family. |
| Evaluation | Visible/private/expected-failing-negative tests in strict normal and fresh ASan/UBSan builds, independent boundary counterexamples, and family/corpus/holdout screening. |
| Generalization target | Distinct coordinate systems and conventions, not renamed, representation-only, width-only, policy-only, or otherwise semantically duplicate generated/benchmark tasks. |

## Prior-finding closure

| Finding | Cycle-02 result | Independent evidence |
| --- | --- | --- |
| CT-AUD-001 | reopened | An initial read-only recomputation matched, but the final freeze check did not. Generated/reverify counts and hashes remain 731 / `sha256:2b16255bd71fb06b0e406ffcd2dc937e0706e7eee1a368532571771ac0a4bbe6` and 709 / `sha256:60697d613b8820cd26893765eb25bf5402b235ff53ba055457a3a26997fc90d8`. Expansion remains 1,640 records but changed from sorted ID/path hash `sha256:822198df09bb8969c9acc7fed78dac5e7f37ef1482f4ff82a0cf0ec78cb13a9a` to `sha256:7f21becc06361fb7156e084bea894ba03fc3183f79ff861926e7104bcf05c350`; `rational-weighted-median` was removed and `rational-amortization-schedule` added. The live all-ID hash is `sha256:5f758b84c7f56c0b00e134f47d6810d19fe0d25551167214068a528a6ee9a7e3`, not the frozen `sha256:bbe797ba5c66a7cc72c062c26b9b6d5385d95faca3f4b783f181378759f1956f`. Regeneration and a fresh screen are required. |
| CT-AUD-002 | closed for its named root and replacement; family remains blocked by CT-AUD-007 | `coord-morton-interleave` is absent. `coord-hex-ring-address` has no ID/exact-content/targeted semantic collision in the 3,080-root comparison inventory. An independent axial-shell walker matched its rank/unrank convention for 1,030,301 cases across radii 0 through 100 and the final cell at radius 1,000,000. Its pinned normal/sanitizer tests and negative discriminator pass. |
| CT-AUD-003 | closed | `coord-quarter-pose` normalizes both headings before bounded addition and forms inverse heading without negating an arbitrary `int`. The exact `INT_MAX + 1` composition and `INT_MIN` inverse cases pass an independent pinned ASan/UBSan build. |
| CT-AUD-004 | closed | `coord-voxel-axis-map` range-checks the signed code before negation/absolute conversion. The exact `INT_MIN` axis-code case passes an independent pinned ASan/UBSan build and returns failure. |
| CT-AUD-005 | closed | `coord-cubemap-edge-step` validates both enum domains before basis or movement dispatch. Exact `static_cast<Face>(99)` and `static_cast<Heading>(99)` cases pass an independent pinned ASan/UBSan build and return failure. An independent 120-transition edge round-trip check found zero failures. |
| CT-AUD-006 | closed | `coord-polyline-frame` handles the exact final segment endpoint before narrowing distance. `{0,0}->{LLONG_MIN,0}` sampled at `2^63` returns the required endpoint/tangent/segment in an independent pinned ASan/UBSan build. |

Closing CT-AUD-002 means only that its named Morton root was replaced by a
valid, distinct axial-shell task. The new CT-AUD-007 demonstrates that the
broader cross-alias clone-control objective is still incomplete for another
retained root.

## Stable new finding

### CT-AUD-007 — high — `coord-quadtree-path` duplicates Morton quadrant-digit encoding

The existing root
`.w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/base-conversion-invalid-digits/basecv-morton-interleave-radix`
converts two coordinates to a top-down sequence of base-four quadrant digits
by pairing one x bit and one y bit at every level, and inversely recovers both
coordinates. Its forbidden substitute is concatenating all x bits and then all
y bits.

`coord-quadtree-path` performs the same encode/decode transform, calls the
digits NW/NE/SW/SE path elements, and rejects the same concatenated-axis-bit
substitute. At `size == 256`, both contracts have exactly eight levels. The
existing root emits digit `2*x_bit + y_bit`; the candidate emits
`x_bit + 2*y_bit`. The fixed bijection
`{0:0, 1:2, 2:1, 3:3}` maps every existing digit to the candidate digit.
Independent exhaustive comparison confirmed this equivalence for all 65,536
8-bit `(x,y)` pairs. Dynamic depth, string versus byte-array storage, compass
labels, and the swapped digit convention are representation/width variations,
not a different primary mechanism.

The generated contamination screen records this subject as passing. Its alias
markers can recognize text that independently contains `morton+interleav` or
`quadtree+quadrant+path`, but do not connect those two names as the same paired
bit/base-four mechanism. The focused regression similarly checks two snippets
that both say Morton; it does not exercise the quadtree alias escape. This is a
concrete false negative in the exact control class that CT-AUD-002 required the
remediation to strengthen.

Disposition: `replace-and-reverify`. Remove `coord-quadtree-path` from the
retained family, generate a semantically new backfill without overwriting any
existing root, and add an adversarial cross-alias control that equates
Morton/interleaved paired bits with quadtree/quadrant-path paired bits despite
digit relabeling and width/representation changes. Then regenerate every root,
rerun creator preflight and fresh normal/sanitizer oracles, and re-audit the new
exact tree.

## Root catalog and dispositions

Every root was inspected from its raw instructions, public header, starter,
reference, visible/private tests, negative implementation, config, and
provenance. `retain-pending-regeneration` is not terminal admission: any
generator-owned replacement changes the family subject and invalidates this
report for final-family verification.

| Root | Capability / tags | Cycle-02 disposition | Finding |
| --- | --- | --- | --- |
| `coord-affine-lattice` | checked arithmetic, affine map, overflow atomicity | retain-pending-regeneration | — |
| `coord-hex-cube-turn` | axial/cube invariant, cyclic orientation | retain-pending-regeneration | — |
| `coord-triangle-barycentric` | exact rational weights, degeneracy, divisibility | retain-pending-regeneration | — |
| `coord-viewport-letterbox` | rational scale, centered padding, pixel mapping | retain-pending-regeneration | — |
| `coord-tile-pyramid-address` | Euclidean division, signed cells, wrap | retain-pending-regeneration | — |
| `coord-hex-ring-address` | axial shell rank/unrank, bounded inverse, replacement lineage | retain-pending-regeneration | CT-AUD-002 closed |
| `coord-hilbert-index` | locality curve, quadrant rotate/reflect, inverse | retain-pending-regeneration | — |
| `coord-utm-zone-band` | half-open geographic partition, named exceptions | retain-pending-regeneration | — |
| `coord-quarter-pose` | pose composition, inverse, modulo heading, extrema | retain-pending-regeneration | CT-AUD-003 closed |
| `coord-isometric-diamond` | sum/difference projection, parity inverse | retain-pending-regeneration | — |
| `coord-projective-rational` | homogeneous transform, gcd normalization | retain-pending-regeneration | — |
| `coord-octant-ring` | unsigned signed-magnitude, boundary precedence | retain-pending-regeneration | — |
| `coord-cubemap-edge-step` | enum validation, face bases, oriented edge transition | retain-pending-regeneration | CT-AUD-005 closed |
| `coord-torus-nearest-delta` | centered modular delta, half-period tie | retain-pending-regeneration | — |
| `coord-voxel-axis-map` | signed permutation, reflection, invalid axes | retain-pending-regeneration | CT-AUD-004 closed |
| `coord-tensor-stride` | mixed-radix strides, axis permutation, capacity | retain-pending-regeneration | — |
| `coord-ragged-linear` | prefix index, empty rows, inverse lookup | retain-pending-regeneration | — |
| `coord-upper-triangle-index` | triangular rank/unrank, monotone search | retain-pending-regeneration | — |
| `coord-quadtree-path` | paired coordinate bits, base-four quadrant digits, inverse | replace-and-reverify | CT-AUD-007 |
| `coord-camera-crop-orient` | crop translation, rotate then mirror | retain-pending-regeneration | — |
| `coord-polyline-frame` | orthogonal prefix selection, vertex handoff, `2^63` endpoint | retain-pending-regeneration | CT-AUD-006 closed |
| `coord-offset-hex-convert` | odd-row/cube conversion, signed parity | retain-pending-regeneration | — |
| `coord-geofence-local` | dateline branch, rational local projection | retain-pending-regeneration | — |
| `coord-integer-shear` | ordered unimodular updates, reverse inverse | retain-pending-regeneration | — |
| `coord-dihedral-canonical` | D4 enumeration, normalization, stable tie | retain-pending-regeneration | — |

Disposition counts: 24 `retain-pending-regeneration`, 1
`replace-and-reverify`, 0 terminally admitted, and 0 irrecoverably rejected.

Potential shared primitives were classified rather than rejected by keyword
alone. For example, `dihedral-shape-classes` floods a grid and returns component
class multiplicities, whereas `coord-dihedral-canonical` transforms one
caller-supplied point set and returns its canonical coordinates plus selected
transform. `symmetric-triangle-packer` encodes a matrix, whereas
`coord-upper-triangle-index` ranks and unranks one storage coordinate. Those
end-to-end contracts are materially distinct. The Morton/quadtree pair is not:
its complete primary encode/decode behavior is identical after a four-symbol
relabel.

## Structure, role, and length audit

- Exactly 25 unique task IDs and exactly 13 non-state files per root are
  present.
- Every config has the exact two editable solution files, two hidden reference
  files, and visible/private tests. The role sets are nonempty, disjoint,
  relative, and resolve to regular single-link files.
- Independent prompt reconstruction found zero `.meta/`, `CMakeLists.txt`,
  private-test, negative, example-source, or reference-prefix leakage.
- Reconstructed prompt sizes range from 2,454 to 3,015 bytes, mean 2,692.12
  bytes. All 25 prompt hashes and all 25 reference-source hashes are unique.
- No candidate ID, exact instructions hash, or exact reference-source hash
  collides with the 3,080 comparison roots.
- Tokenizer measurement and assistant-loss masking remain inapplicable: this
  is a local task-family verification, not JSONL/SFT admission. No dataset
  release or train-readiness claim is made.

## Runtime and independent correctness evidence

The bound Docker receipt contains 25 root records and three control records.
Every record reports three discovered and passing CTests in normal mode and the
same three in a fresh sanitizer build; every direct negative executable exits
nonzero. This is 150 discovered root test executions plus 18 control test
executions, with 56 additional direct negative executions across both modes.

The cycle-02 auditor independently bypassed the owner/CMake receipt and, in the
same pinned no-network image, directly compiled each raw `.meta/example.cpp`
against both `visible_test.cpp` and `.meta/private_test.cpp` with
`-fsanitize=address,undefined`, then compiled each raw negative implementation
against its private test. All 50 reference test binaries exited zero and all 25
negative binaries exited nonzero. Separate exact-case execution confirmed the
four CT-AUD-003 through CT-AUD-006 counterexamples. These executable checks do
not cure CT-AUD-007 because that finding concerns duplicate teaching behavior,
not reference correctness.

## Diversity and adversarial clone controls

The generated screen contains all 300 unordered candidate pairs in all seven
required dimensions. The highest retained-pair score remains below its
threshold in every dimension:

| Dimension | Maximum | Threshold |
| --- | ---: | ---: |
| public API | 0.776786 | 0.81 |
| owned state or algorithm | 0.723481 | 0.82 |
| mutation or selection rules | 0.486144 | 0.82 |
| invalid and boundary behavior | 0.821284 | 0.83 |
| reference control flow | 0.580421 | 0.82 |
| deterministic oracle | 0.808478 | 0.82 |
| topic-specific negative fixture | 0.629177 | 0.82 |

The three materialized torus-derived controls mutate nonempty artifact sets:
domain/identifier rename changes 11 files, constants/policy-only changes 3,
and opposite-end selection changes 7. Each remains coherent, passes normal and
fresh sanitizer behavior execution, and is rejected as a clone in all seven
dimensions.

Those controls validate the recorded near-clone classes only. CT-AUD-007 is
direct evidence that the evaluator's lexical alias layer does not cover a
representation-preserving rename between Morton interleave and quadtree path
terminology. Numeric threshold passage cannot override that exact semantic
equivalence.

## Duplicate, lineage, and contamination report

- The final live comparison inventory no longer matches the frozen inventory.
  It still has 3,080 records, 2,991 unique IDs, and 89 reserved lineage
  collisions, and none uses a candidate ID, but one expansion root was replaced
  after creator preflight. See reopened CT-AUD-001.
- Within the candidate subject, no exact ID, prompt, instructions, or reference
  duplicate exists. All provenance records declare `lineage: new-root`,
  clean-room repository authoring, CC0-1.0, and the local-only nonclaim.
- The generated contamination screen binds the now-stale frozen inventory hash,
  all 26 official Aider C++ holdouts, and 77,650 comparisons. It reports maximum
  lexical semantic Jaccard 0.256579 and no holdout leak for that frozen set, but
  25 candidate-to-foreign comparisons are now missing and 25 stale comparisons
  remain because of the one-for-one root replacement.
- The old `coord-morton-interleave` candidate is absent. The replacement
  `coord-hex-ring-address` is a new axial shell rank/unrank contract; targeted
  raw-corpus searches found no other hex shell/ring rank/index task. The
  existing `axial-hex-ascii-map` performs staggered text projection and is not
  an equivalent contract.
- `coord-quadtree-path` is a semantic duplicate despite having no exact hashes
  or ID collision. See CT-AUD-007. This false negative blocks the generated
  contamination receipt's family-level pass claim.
- No hidden benchmark answer, private test, reference source, or evaluator
  rubric was found in a public prompt. No train/validation/test split or
  selected training manifest exists or is authorized.

## Decision and limitations

Decision for exact subject
`sha256:20263dbc7b439dfb944721fd4e691a97b9b04890af35a0a432c04b9258d97c04`:
**`not_completed`**.

Confirmed: exact raw structure, current inventory binding, role separation,
the repaired boundary behavior, reference/negative execution, the valid axial
hex backfill, generated seven-dimension evidence, and holdout screening.

Blocking: reopened CT-AUD-001 invalidates the current corpus-screen binding,
and CT-AUD-007 leaves only 24 retainable roots while demonstrating a cross-alias
semantic-duplicate escape. No 25-root `local_family_verified` claim is
supported until a new exact regenerated family passes creator preflight and
another independent audit.

This audit makes no JSONL, tokenizer/mask, split, dataset-release, training,
benchmark-uplift, or model-quality claim.
