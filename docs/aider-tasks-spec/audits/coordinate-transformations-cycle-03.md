# Coordinate Transformations Expansion: Independent Audit Cycle 03

Audit date: 2026-07-22
Audit subject: `.w8-biayn/data/aider-tasks-expansion-v1/text-grid/coordinate-transformations/`
Decision: **`not_completed`**

## Result first

The exact regenerated subject contains 25 candidate roots and 325 non-state
task files. Its independently recomputed owner-policy tree hash is
`sha256:14f68d665e9c1a8c09c2a73a540acc49668b10f1eeea3b82636e6aa3609b1066`,
matching the manifest, creator-preflight receipt, Docker receipt, and supplied
cycle-03 subject.

All named duplicate roots from the earlier audits are absent. The
`coord-hex-ring-address` and `coord-reflective-boundary-fold` replacements are
correct on fresh, independently derived property checks and add distinct
primary mechanisms. The Morton/quadtree cross-alias control is materialized
and rejects the representation-preserving paired-bit alias. The exact
CT-AUD-003 through CT-AUD-006 regressions pass fresh raw-reference sanitizer
execution.

The family is nevertheless not locally verified. Two hard gates are open at
the final audit freeze:

- **CT-AUD-001 (reopened):** the candidate subject is unchanged, but 56 roots
  under the foreign `bounded-circular-storage` and
  `modular-clock-normalization` families were replaced after the
  cycle-03 inventory was frozen. The expansion count remains 1,640, while its
  ID/path hash changed from
  `sha256:e59b3868355d4d8dc012e39e1ed8d5dcf875dc7bc7c2d308be71c097ed51f72e`
  to
  `sha256:066cde45f442534c5dc932615112418c6f5060ceae9d3e3eb28283c3c57693b4`.
  The all-ID hash changed from
  `sha256:0f3590c08191dba064a0a9eeab47ef0243fff918d6bc5df79ec1f872464cf4d6`
  to
  `sha256:861aa7ac388e10fded101c363b94c296a2c073fabc44d35f9d82aef2c6d0f7e6`.

- **CT-AUD-008:** `coord-polyline-frame` validates segments only while
  traversing toward the requested distance. It returns from an early valid
  segment without validating a later diagonal or zero-length segment, despite
  the contract requiring every segment to be orthogonal and nonzero.

Cycle 03 therefore assigns 24 roots `retain-pending-regeneration` and one root
`repair-and-reverify`. No root is terminally admitted while the exact family
subject is blocked. Required next steps are generator-owned repair of
CT-AUD-008, regeneration after the comparison inventory is stable, creator
preflight, fresh normal/sanitizer oracle evidence, and another independent
audit of that new exact tree.

## Frozen subject and evidence

| Evidence | SHA-256 or value |
| --- | --- |
| Candidate tree, excluding `.state` by owner policy | `sha256:14f68d665e9c1a8c09c2a73a540acc49668b10f1eeea3b82636e6aa3609b1066` |
| Non-state roots / files | `25 / 325` |
| Owner | `sha256:f1cbafae8545904a189c638333b797bc6a4c31100008fe526611e9f95dee02b2` |
| Curriculum | `sha256:dc1d4132d81982fb0a8fe11c3aa694f8eb51c750b9f09780982f2594e126d0d2` |
| Family specification | `sha256:1ec45c8afd934e197fb6155d1b79d9bc3574014bc1477bfa9c2d4989ac0e04a4` |
| Focused tests | `sha256:82ccc9454a5678d7ff708bd2d8803ece616a67a632a38cd3a68cd9567009fc3b` |
| Manifest bytes | `sha256:025d6f49856794a1adeebb9565bd7eee75429d8d51827096552a1d9bea53860e` |
| Frozen source inventory bytes | `sha256:e7437c153aa36ac97fa15c99fb2cbebdae740193eb122b3196d4819752554db4` |
| Diversity screen bytes | `sha256:fb302c9b5bf318319549e22a41493ffe6bce86e2cceacf14616dc264a44787cd` |
| Contamination screen bytes | `sha256:eb32820d22c62c9f59dea54c4421e4035aabf5f64af965843e4d3a7e31f4ca3b` |
| Cross-alias control bytes | `sha256:397daeed5e2a89bc726addf523edca4a41a260a3d9894b254426d0eded77b58c` |
| Docker-sanity receipt bytes | `sha256:d116a56216d6d42521639851b89a148316d87e15f2431aa9c86242863edf4224` |
| Creator-preflight receipt bytes | `sha256:ccd047a5042db537721d670bed015ad9c839ad7dbc4209d2b58f3e6ac7b9808b` |
| Cycle-03 creator receipt bytes | `sha256:b12831c54b3091662a8f75fb7c2090d3c5477899fd1fe18991dd8d7d51b70c1d` |
| Root-status bytes | `sha256:56ea648e74fa986158471805c0bcd72bab06e24c0e1dc2a86606f36c7c73eb75` |
| Immutable cycle-01 report | `sha256:e4b83295702acb04e19e49001146917a8fef052f4e47b36e79e79dc1773c15b9` |
| Immutable cycle-02 report | `sha256:1e9f1778a8176e06acb3734241b1b92e660f4d93795eef8c12fb82d5a25c10a4` |

The creator runtime receipt binds image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
the identical image ID, network policy `none`, GCC 13.4.0 at
`/usr/local/bin/g++` with compiler hash
`sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
and CMake 3.25.1. This is repository Docker-sanity evidence, not a locked
family-specific oracle.

The auditor read all eight owner remedy records. Their exact hashes are:

| Remedy record | SHA-256 |
| --- | --- |
| cycle 01 CT-AUD-001 | `sha256:2453704594ba133ab19063585ffbb36aab0904e99ca1414b81c611f570f9bee6` |
| cycle 01 CT-AUD-002 | `sha256:b771d61978edb86474c40f55d722415ea44a428c1938a6525628fd62c067d601` |
| cycle 01 CT-AUD-003 | `sha256:468abd5f220e25b9ab1a51c58257403e081d3a208811ec6796f6ae484bf09cf0` |
| cycle 01 CT-AUD-004 | `sha256:dc69af2d1e73b2bed59370310018879ed2cb252773c48698aeaeba896aec9d74` |
| cycle 01 CT-AUD-005 | `sha256:eca400b50669442735b8365ad1064b6970d200898ce765306237b6a6e8971b48` |
| cycle 01 CT-AUD-006 | `sha256:361ce5dddfea88c2661738a49efd5f5aa7e0b18ac3b35bcd184cb13dc1c3e8eb` |
| cycle 02 CT-AUD-001 | `sha256:6f550e99c357a2417100287012b49869dce2d5a2b0666d865e6d8e19f2214ad3` |
| cycle 02 CT-AUD-007 | `sha256:ee482ca0b017895fc9ca5e008d064e36f9b63ba2a22e1961708facbb8075327a` |

## Behavior contract used for audit

| Field | Contract |
| --- | --- |
| Task | Implement each declared C++17 coordinate transformation exactly. |
| Inputs | Only typed public API values; deterministic, offline, standard library only. |
| Output | Complete replacements for the declared header and source, with no other files or prose. |
| Invariants | Exact public API, failure-atomic invalid return, checked arithmetic, documented orientation/order/tie policy, and no private-role leakage. |
| Failure behavior | Invalid or unrepresentable inputs return the documented empty/false optional result without partial output or undefined behavior. Whole-input validity requirements apply before a successful partial traversal result is returned. |
| Resource limits | No network or third-party dependency; finite public domains where stated. No SFT token/context limit is authorized for this local family. |
| Evaluation | Visible/private/expected-failing-negative tests in strict normal and fresh ASan/UBSan builds, independent boundary/property counterexamples, and family/corpus/holdout screening. |
| Generalization target | Distinct coordinate systems and conventions, not renamed, representation-only, width-only, policy-only, or otherwise semantically duplicate generated/benchmark tasks. |

## Prior-finding closure

| Finding | Cycle-03 result | Independent evidence |
| --- | --- | --- |
| CT-AUD-001 | reopened | The first read-only recomputation matched the frozen 731 generated, 709 reverify, and 1,640 expansion records. At the final freeze, generated and reverify were unchanged, but 56 foreign expansion records had been replaced by 56 new records under `state-concurrency/bounded-circular-storage` and `time-date/modular-clock-normalization`. The exact signed ID/path delta hashes to `sha256:c3baddc36e498c39cf929e690c70014b09784c13e28233b2f68c5b754e7f7202`; removed IDs hash to `sha256:4f25ae17706b592dc48152f57d18667c71bdec33a6355a33911be40fca3b224e`, and added IDs hash to `sha256:895d7d125f5bb16c7817ee8f7b005ad33b08431343dc1ccaad3ee689fabb5269`. The live inventory still has 2,991 unique IDs and 89 reserved lineage collisions, but no longer binds the generated contamination receipt. |
| CT-AUD-002 | closed | `coord-morton-interleave` is absent. Fresh answer-blind property execution checked `coord-hex-ring-address` against an independently derived six-side axial walker for all 270,901 cells through radius 300 and the exact final cell at radius 1,000,000. Targeted raw-corpus search found no foreign axial hex shell/ring rank-address contract. |
| CT-AUD-003 | closed | The exact `INT_MAX + 1` composition and `INT_MIN` inverse-heading cases pass direct compilation of the raw quarter-pose reference and private test under fresh ASan/UBSan. Operands are normalized before bounded heading combination. |
| CT-AUD-004 | closed | The exact `INT_MIN` axis-code case passes direct raw-reference sanitizer execution and returns failure before any negation or absolute-value conversion. |
| CT-AUD-005 | closed | Invalid `Face(99)` and `Heading(99)` values pass direct raw-reference sanitizer execution by returning failure before basis or movement dispatch. |
| CT-AUD-006 | closed for the exact endpoint defect | The exact `{0,0}->{LLONG_MIN,0}` sample at distance `2^63` returns the required final endpoint, tangent, and segment under direct raw-reference ASan/UBSan execution. CT-AUD-008 is a different whole-polyline validity defect in the same root. |
| CT-AUD-007 | closed | `coord-quadtree-path` is absent. Fresh property execution checked `coord-reflective-boundary-fold` over 1,980,099 dense integer phases, signed extrema, singleton axes, and boundary-direction policy. Targeted raw-corpus search found no foreign triangle-wave reflective-box fold. The materialized `morton-quadtree-paired-bit-digit-relabel` control joins Morton/interleave and quadtree/quadrant-path terminology and records `duplicate_family`. |

## Stable new finding

### CT-AUD-008 — high — `coord-polyline-frame` accepts an invalid suffix

The task specification requires at least two points and says **every** segment
must be orthogonal and nonzero. The public instructions likewise state that
diagonal and zero-length segments reject.

The reference iterates over segments, but when `distance < len` it immediately
returns the sample from the current segment. It has not inspected any later
segments at that point. Therefore both calls below return engaged optionals:

```cpp
sample_polyline({{0,0}, {10,0}, {11,1}}, 1);   // diagonal suffix
sample_polyline({{0,0}, {10,0}, {10,0}}, 1);   // zero-length suffix
```

A fresh no-network compile of the exact raw reference with GCC 13.4.0 and
`-fsanitize=address,undefined` used a discriminator that returned zero only if
both calls rejected. It exited 17. The existing private test checks a diagonal
or zero-length first segment, so it does not cover this traversal-order escape.

Disposition: `repair-and-reverify`. Validate all segments and checked segment
lengths before selecting any sample, or otherwise guarantee a complete
validation pass before return. Add both invalid-suffix counterexamples to
normal and sanitizer tests. Regenerate the exact family and rerun every
artifact-bound screen and independent audit; a hand edit to the materialized
root is not admissible.

## Root catalog and dispositions

Every root was inspected from raw instructions, header, starter, reference,
visible/private tests, negative implementation, config, and provenance. Root
hashes cover all 13 files in each root. `retain-pending-regeneration` is not
terminal admission: repairing one root and rebinding the corpus creates a new
family subject.

| Root | Root SHA-256 | Capability / tags | Cycle-03 disposition | Finding |
| --- | --- | --- | --- | --- |
| `coord-affine-lattice` | `sha256:50b9538f5e2964bae133477b88b4f022a3490daefd580a13187ef331ceaa5c88` | checked affine map; overflow atomicity | retain-pending-regeneration | — |
| `coord-hex-cube-turn` | `sha256:33d7514411145b86966191e3c12e9758e27d29e81ba64e472de0d5d28c3fab2d` | cube invariant; cyclic orientation | retain-pending-regeneration | — |
| `coord-triangle-barycentric` | `sha256:c395b411ed5248521e6808986335f3e28260247e4787109a7d5db605204fb1dd` | exact rational weights; degeneracy | retain-pending-regeneration | — |
| `coord-viewport-letterbox` | `sha256:8e6a9456067237f2d2bca3f410c45431bd83228ac57fc97e08b6201f0bcb2fd0` | rational limiting scale; centered padding | retain-pending-regeneration | — |
| `coord-tile-pyramid-address` | `sha256:608fbaa1aee97dd0c16d210aedc89e6ae2c174fc910b63dc91d662fe64e633c3` | Euclidean tile division; horizontal wrap | retain-pending-regeneration | — |
| `coord-hex-ring-address` | `sha256:23ebbf7a062c70fd3771c58f1e996df472d9a73ceb6447f6f7936ce723406ca5` | axial shell rank/unrank; replacement lineage | retain-pending-regeneration | CT-AUD-002 closed |
| `coord-hilbert-index` | `sha256:6893e754285b5a717bcb10d5d9c91fc662703998cb37c1eb2fe35a688b59f273` | Hilbert rotation/reflection; round trip | retain-pending-regeneration | — |
| `coord-utm-zone-band` | `sha256:ae1e57d3309a77e931df6e11419559df2cf5a82a9402bfb947900901b319c3e9` | half-open geographic partition; exceptions | retain-pending-regeneration | — |
| `coord-quarter-pose` | `sha256:0bfac14952b490ed6337fcd514c3572c5a0f3e58ee33dd251bc5a1c770c64eb8` | pose composition/inverse; modulo extrema | retain-pending-regeneration | CT-AUD-003 closed |
| `coord-isometric-diamond` | `sha256:0f1e20f69f1b994e83e34db4bfc9169a5dd9089ba3f140446d0cd93b873e1525` | sum/difference projection; parity inverse | retain-pending-regeneration | — |
| `coord-projective-rational` | `sha256:29f4ef6c4d7ea2e3a8fe492d65ca497bb97e00db91acfe58cea84e0287a34e3c` | homogeneous transform; gcd normalization | retain-pending-regeneration | — |
| `coord-octant-ring` | `sha256:fdb0d47d17a776547657f1255bb3e23def1bcb2c236f4b20a8bc053df7f8fd33` | unsigned signed-magnitude; boundary precedence | retain-pending-regeneration | — |
| `coord-cubemap-edge-step` | `sha256:6c23c355fd2f5ab2d2d45ddc5dafdf79c9c5d904a7702a30f4fb652f71cc948c` | validated enums; face-basis edge transition | retain-pending-regeneration | CT-AUD-005 closed |
| `coord-torus-nearest-delta` | `sha256:38241b5579127b3435b3ce1938a43fabd9fdb5aa87572bd7eee3a7950c681847` | centered modular delta; half-period tie | retain-pending-regeneration | — |
| `coord-voxel-axis-map` | `sha256:932ab6581fdfc6711e67ab0e7761556fcc39829c7ff1fffa1fee4d467db59bd4` | signed permutation; invalid-axis extrema | retain-pending-regeneration | CT-AUD-004 closed |
| `coord-tensor-stride` | `sha256:e74526a7d3e82df4cca6263e9b8abad22069444bacce9d06b5a5c2e87a61e90e` | mixed-radix strides; axis permutation | retain-pending-regeneration | — |
| `coord-ragged-linear` | `sha256:47b4f8e961fabd5b4668feddab554c957dff9d074acc62707f3fbc81f539a16c` | prefix index; empty-row inverse lookup | retain-pending-regeneration | — |
| `coord-upper-triangle-index` | `sha256:e0bdee0d001d490cbbaa22849914bc19b39a0688a5282318ef9e7faa2f65662b` | triangular rank/unrank; monotone search | retain-pending-regeneration | — |
| `coord-reflective-boundary-fold` | `sha256:73fe82eb0bffaf89d0936f3d0532f6b739cc8f608abd611a891d90660bd9cbbc` | triangle-wave fold; branch direction; replacement lineage | retain-pending-regeneration | CT-AUD-007 closed |
| `coord-camera-crop-orient` | `sha256:e13bab626f6ac537de32ae440785cc157bda7c86b0305c76401f40626507a273` | crop translation; rotate then mirror | retain-pending-regeneration | — |
| `coord-polyline-frame` | `sha256:9f86ba29d09f3ae4603a720000da76272467d9c2abd73aa6aae4b5cb787826f6` | orthogonal prefix selection; vertex handoff | repair-and-reverify | CT-AUD-008 |
| `coord-offset-hex-convert` | `sha256:4587354e3e008b8ed70fef957d1721fd5abd541587518e479439c6aeeb856fe4` | signed odd-row/cube conversion | retain-pending-regeneration | — |
| `coord-geofence-local` | `sha256:c22cdb364b29b4e504a329b67b60ee6f74305f3b23fd106827f67ede7edceaed` | dateline branch; checked rational scale | retain-pending-regeneration | — |
| `coord-integer-shear` | `sha256:d18148e53a71b11e04c3a1bdb0035c147eacb58d56d714b6c6039206d41e4fa6` | ordered unimodular updates; reverse inverse | retain-pending-regeneration | — |
| `coord-dihedral-canonical` | `sha256:ec0ba2b0e947e674ac91d7316b46ebccb7cbc9b0a8a95745cc3d08d0c71388b0` | D4 enumeration; normalized stable tie | retain-pending-regeneration | — |

Disposition counts: 24 `retain-pending-regeneration`, 1
`repair-and-reverify`, 0 terminally admitted, and 0 irrecoverably rejected.

## Structure, role, and length audit

- Exactly 25 unique IDs and exactly 13 files per non-state root are present.
- Every config has two editable solution files, two hidden reference files,
  and visible/private tests. Role sets are nonempty, disjoint, relative, and
  resolve to regular single-link files.
- Independent prompt reconstruction found no `.meta/`, CMake, private-test,
  negative-source, example-source, or substantive reference-body leakage.
- Exact Aider-like prompts range from 2,454 to 3,015 bytes, mean 2,698.32
  bytes. All 25 prompt hashes and all 25 raw reference hashes are unique.
- No candidate ID, exact instruction hash, or exact reference-source hash
  collides with the comparison roots present during the audit. The final
  56-for-56 inventory replacement still invalidates the bound semantic screen.
- Tokenizer measurement and assistant-loss masking are inapplicable: this is
  local task-family verification, not JSONL/SFT admission.

## Runtime and negative-discriminator evidence

The bound Docker receipt contains 25 root records and three coherent clone
control records. Every record reports three discovered and passing CTests in
normal mode and the same three in a fresh sanitizer build; every direct
negative executable exits nonzero. That receipt covers 150 root CTest
executions, 18 control CTest executions, and 56 direct negative executions.

The cycle-03 auditor independently bypassed the owner/CMake verdict and
directly compiled every raw `.meta/example.cpp` against both
`visible_test.cpp` and `.meta/private_test.cpp` with ASan/UBSan in the pinned
no-network image. All 50 reference binaries exited zero. Every raw negative
implementation compiled and its private-test binary exited nonzero. The
integer-shear negative also emits the expected UBSan diagnostic when it
blindly negates `LLONG_MIN`; this remains evidence against that unchecked
substitute, not a sanitizer failure in the retained reference.

Those passes do not close CT-AUD-008: the independent invalid-suffix
counterexample lies outside the generated suite and deterministically
contradicts the raw contract.

## Diversity, lineage, and contamination audit

The generated diversity artifact contains all 300 unordered candidate pairs
in all seven required dimensions. Its maximum retained-pair scores remain
below their thresholds:

| Dimension | Maximum | Threshold |
| --- | ---: | ---: |
| public API | 0.776786 | 0.81 |
| owned state or algorithm | 0.723481 | 0.82 |
| mutation or selection rules | 0.486144 | 0.82 |
| invalid and boundary behavior | 0.821284 | 0.83 |
| reference control flow | 0.580421 | 0.82 |
| deterministic oracle | 0.788323 | 0.82 |
| topic-specific negative fixture | 0.629177 | 0.82 |

The torus-derived domain/identifier, constants/policy, and opposite-end
controls mutate 11, 3, and 7 files respectively. Each executes in normal and
fresh sanitizer modes and is rejected as a clone in all seven dimensions.
The separate Morton/quadtree control explicitly connects the two terminology
families despite digit relabeling and width/representation changes.

Within the candidate subject there are no exact ID, prompt, instruction,
reference, or root duplicates. All provenance records declare clean-room
`new-root` lineage, CC0-1.0, and the local-only nonclaim. Targeted semantic
searches found no foreign hex-shell rank/unrank or reflective triangle-wave
fold. Shared concepts were classified rather than rejected: for example, the
newly observed foreign `floor-mod-torus-grid` is a mutable fixed grid with
wrapped lookup/window operations, whereas `coord-torus-nearest-delta`
computes a stateless shortest displacement with a half-period tie policy.

The generated contamination receipt binds 3,080 comparison roots, all 26
official Aider C++ holdouts, and 77,650 comparisons. It reports maximum lexical
Jaccard 0.256579 and no leak for its frozen inventory. At final freeze, 1,400
candidate-to-foreign comparisons are stale and 1,400 current comparisons are
missing because 56 comparison roots were replaced. Thus the receipt's
family-level pass cannot be retained, irrespective of the targeted checks.
No train/validation/test split or selected training manifest exists or is
authorized.

## Decision and limitations

Decision for exact subject
`sha256:14f68d665e9c1a8c09c2a73a540acc49668b10f1eeea3b82636e6aa3609b1066`:
**`not_completed`**.

Confirmed: exact raw structure and subject binding, closure of named
CT-AUD-002 through CT-AUD-007 defects, correctness and novelty of both
replacement roots, direct reference/negative sanitizer execution, role
separation, and seven-dimension/adversarial-control coverage.

Blocking: CT-AUD-001 is reopened by final comparison-inventory drift, and
CT-AUD-008 leaves only 24 retainable roots by accepting a polyline with an
invalid suffix. No 25-root `local_family_verified` claim is supported until a
new generator-owned subject passes creator preflight and another independent
audit.

This audit makes no JSONL, tokenizer/mask, split, dataset-release, training,
benchmark-uplift, or model-quality claim.
