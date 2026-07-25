# Coordinate Transformations Expansion: Independent Audit Cycle 04

Audit date: 2026-07-22
Audit subject: `.w8-biayn/data/aider-tasks-expansion-v1/text-grid/coordinate-transformations/`
Decision: **`local_family_verified`**

## Result first

The exact regenerated subject contains 25 candidate roots and 325 non-state
task files. Its independently recomputed owner-policy tree hash is
`sha256:566f9fcf3ca93f7724aa064a03e329a888dcfb82e7bfb691829ba59728296671`.
That hash matches the manifest, creator preflight, Docker receipt, mounted
snapshot, root-status ledger, and cycle-04 audit subject.

All eight stable findings from cycles 01 through 03 are closed on this exact
tree. In particular:

- the final read-only inventory freeze exactly matches the materialization
  inventory at 731 generated, 709 reverify, and 1,640 foreign expansion roots;
- both semantic-duplicate roots, `coord-morton-interleave` and
  `coord-quadtree-path`, are absent;
- both replacement roots are correct under fresh independently derived
  property checks and are semantically novel in the live corpus;
- the Morton/quadtree representation-alias control records and rejects the
  paired-bit mechanism despite width, representation, and vocabulary changes;
- every cycle-01 boundary counterexample passes direct raw-reference sanitizer
  execution; and
- `coord-polyline-frame` validates the complete input before selection and
  rejects both a diagonal suffix and a zero-length suffix.

The auditor independently compiled every raw reference against its visible and
private tests and every raw negative against the private test in the pinned
no-network image with fresh ASan/UBSan instrumentation. All 50 reference
executions passed and all 25 negatives were rejected. Fresh property harnesses
for both replacement roots and fresh direct execution of all three adversarial
controls also passed.

No unresolved hard gate remains. All 25 roots receive the terminal local-family
disposition `retain`; the exact subject decision is `local_family_verified`.
This is not dataset-release or training admission.

## Frozen subject and evidence

| Evidence | SHA-256 or value |
| --- | --- |
| Candidate tree, excluding `.state` by owner policy | `sha256:566f9fcf3ca93f7724aa064a03e329a888dcfb82e7bfb691829ba59728296671` |
| Non-state roots / files | `25 / 325` |
| Owner | `sha256:0820bee5146931662495ef6db3de5b071ec7d075320c1b71f4a6f39f273f7e40` |
| Curriculum | `sha256:dc1d4132d81982fb0a8fe11c3aa694f8eb51c750b9f09780982f2594e126d0d2` |
| Family specification | `sha256:1ec45c8afd934e197fb6155d1b79d9bc3574014bc1477bfa9c2d4989ac0e04a4` |
| Focused tests | `sha256:82ccc9454a5678d7ff708bd2d8803ece616a67a632a38cd3a68cd9567009fc3b` |
| Manifest bytes | `sha256:8e481e92e560f9b881003ede1bad92748ca6e0db4378ebca275d1b864dacf9db` |
| Frozen source inventory bytes | `sha256:ba3ce743a3c300bd13f2f0fc1e2013373a98aba9ac391ff319aeefe05079a3d2` |
| Diversity screen bytes | `sha256:ecaa00324c6ac4d2176877728fb9b1afd2d0b50252a6f2e0d2ef45cf8eba4114` |
| Contamination screen bytes | `sha256:6cf9909ea2e14caf552f162838c8349e8d064c1e4ec630cc3b08ae0070d93501` |
| Adversarial-control manifest bytes | `sha256:3026d35e39afd6d3bc11cee38a5c9ca88d97f842b375d4bce02fd007284b505c` |
| Cross-alias control bytes | `sha256:397daeed5e2a89bc726addf523edca4a41a260a3d9894b254426d0eded77b58c` |
| Docker-sanity receipt bytes | `sha256:9c7160e1b156e9dcf073cabd90b493347ab555c0b0bbdc99e5639a4f1a90598d` |
| Creator-preflight receipt bytes | `sha256:c6f723598b20dcb0948b04ffa1c3ef892a6b2ca02b7300de79e0ae273e7eae4b` |
| Cycle-04 creator receipt bytes | `sha256:1c142cdec0613efee267a10656ac75c62f19a9c64d3dd14e932d3c97e1e1f5b9` |
| Root-status bytes | `sha256:fee29730ce3eb7c1245ac9172371158ea4ce43ad8ffd409e358ddcdcc1d21109` |
| Immutable cycle-01 report | `sha256:e4b83295702acb04e19e49001146917a8fef052f4e47b36e79e79dc1773c15b9` |
| Immutable cycle-02 report | `sha256:1e9f1778a8176e06acb3734241b1b92e660f4d93795eef8c12fb82d5a25c10a4` |
| Immutable cycle-03 report | `sha256:829397e4f0a1d160e749d054640810850a15eb1e68861047d51a19aee9c88255` |

The creator runtime receipt binds image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
the identical image ID, network policy `none`, GCC 13.4.0 at
`/usr/local/bin/g++` with compiler hash
`sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
and CMake 3.25.1. The mounted, live, and receipt tree hashes agree. This remains
repository Docker-sanity evidence rather than a family-specific locked grader.

All ten immutable remedy records were read and their hashes match the cycle-04
creator receipt:

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
| cycle 03 CT-AUD-001 | `sha256:e473ceb783c56f82ee88829a12d4cc525b73f90e8cc31dec138ad1913e372b03` |
| cycle 03 CT-AUD-008 | `sha256:05d6c3aaef99c6f3d090f9f9d1bf3f0a32d8b6722f5659222577ffbb4536aad3` |

## Behavior contract used for audit

| Field | Contract |
| --- | --- |
| Task | Implement each declared C++17 coordinate transformation exactly. |
| Inputs | Only typed public API values; deterministic, offline, standard library only. |
| Output | Complete replacements for the declared header and source, with no other files or prose. |
| Invariants | Exact public API, failure-atomic invalid return, checked arithmetic, documented orientation/order/tie policy, and no private-role leakage. |
| Failure behavior | Invalid or unrepresentable inputs return the documented empty/false optional result without partial output or undefined behavior; whole-input validity precedes a successful partial traversal result. |
| Resource limits | No network or third-party dependency; finite public domains where stated. No SFT token/context limit is authorized for this local family. |
| Evaluation | Visible/private/expected-failing-negative tests in strict normal and fresh ASan/UBSan builds, independent property and boundary counterexamples, and candidate/corpus/holdout screening. |
| Generalization target | Distinct coordinate systems and conventions, not renamed, representation-only, width-only, policy-only, or otherwise semantically duplicate generated/benchmark tasks. |

## Prior-finding closure

| Finding | Cycle-04 result | Independent evidence |
| --- | --- | --- |
| CT-AUD-001 | closed | Immediately before this report was frozen, an independent inventory recomputation exactly matched all three stored count and sorted ID/path hashes: generated `731` / `sha256:2b16255bd71fb06b0e406ffcd2dc937e0706e7eee1a368532571771ac0a4bbe6`, reverify `709` / `sha256:60697d613b8820cd26893765eb25bf5402b235ff53ba055457a3a26997fc90d8`, and foreign expansion `1,640` / `sha256:066cde45f442534c5dc932615112418c6f5060ceae9d3e3eb28283c3c57693b4`. The stored and live inventories both contain 2,991 unique IDs with `all_ids_hash=sha256:861aa7ac388e10fded101c363b94c296a2c073fabc44d35f9d82aef2c6d0f7e6`; their ID sets and 89 reserved-lineage collision maps also match. |
| CT-AUD-002 | closed | `coord-morton-interleave` is absent. A fresh answer-blind six-direction axial-shell walker checked both directions of `coord-hex-ring-address` for all 270,901 cells through radius 300 plus the first and last cells at radius 1,000,000 under ASan/UBSan. Targeted live-corpus search found no other axial ring/shell rank-address contract. |
| CT-AUD-003 | closed | Direct raw-reference sanitizer execution passes the exact `INT_MAX + 1` quarter-heading composition and `INT_MIN` inverse-heading cases. Operands are normalized before bounded addition and no unnormalized minimum value is negated. |
| CT-AUD-004 | closed | Direct raw-reference sanitizer execution rejects `INT_MIN` as an invalid axis code before absolute-value conversion and rejects negation of a valid axis selecting an `LLONG_MIN` coordinate. |
| CT-AUD-005 | closed | Direct raw-reference sanitizer execution rejects both `Face(99)` and `Heading(99)` before basis or movement dispatch. |
| CT-AUD-006 | closed | Direct raw-reference sanitizer execution returns the exact `{0,0}->{LLONG_MIN,0}` endpoint at unsigned distance `2^63`, with tangent `{-1,0}` and segment zero, without narrowing that endpoint distance. |
| CT-AUD-007 | closed | `coord-quadtree-path` is absent. A fresh answer-blind property harness checked `coord-reflective-boundary-fold` for 2,000,100 dense `(extent,value)` cases, signed extrema, singleton axes, and both endpoint branch policies under ASan/UBSan. Targeted live-corpus search found no other triangle-wave reflective-box transform. The cross-alias control joins Morton/interleave and quadtree/quadrant-path terms and records `duplicate_family`. |
| CT-AUD-008 | closed | The exact raw reference first validates and stores every segment length and tangent, then performs selection. Fresh sanitizer execution rejects `{{0,0},{10,0},{11,1}}` at distance 1 and `{{0,0},{10,0},{10,0}}` at distance 1. Both invalid-suffix cases are now in the private oracle, and the full private executable passes. |

## Root catalog and dispositions

Every root was inspected from raw introduction, instructions, public header,
starter source, reference header/source, visible/private tests, negative source,
config, tests metadata, and provenance. Root hashes cover all 13 files. `retain`
means retained in this exact verified local family; it does not authorize SFT
projection, release, or training.

| Root | Root SHA-256 | Capability / tags | Disposition |
| --- | --- | --- | --- |
| `coord-affine-lattice` | `sha256:50b9538f5e2964bae133477b88b4f022a3490daefd580a13187ef331ceaa5c88` | checked affine map; overflow atomicity | retain |
| `coord-hex-cube-turn` | `sha256:33d7514411145b86966191e3c12e9758e27d29e81ba64e472de0d5d28c3fab2d` | cube invariant; cyclic orientation | retain |
| `coord-triangle-barycentric` | `sha256:c395b411ed5248521e6808986335f3e28260247e4787109a7d5db605204fb1dd` | exact rational weights; degeneracy | retain |
| `coord-viewport-letterbox` | `sha256:8e6a9456067237f2d2bca3f410c45431bd83228ac57fc97e08b6201f0bcb2fd0` | rational limiting scale; centered padding | retain |
| `coord-tile-pyramid-address` | `sha256:608fbaa1aee97dd0c16d210aedc89e6ae2c174fc910b63dc91d662fe64e633c3` | Euclidean tile division; horizontal wrap | retain |
| `coord-hex-ring-address` | `sha256:23ebbf7a062c70fd3771c58f1e996df472d9a73ceb6447f6f7936ce723406ca5` | axial shell rank/unrank; replacement lineage | retain |
| `coord-hilbert-index` | `sha256:6893e754285b5a717bcb10d5d9c91fc662703998cb37c1eb2fe35a688b59f273` | Hilbert rotation/reflection; round trip | retain |
| `coord-utm-zone-band` | `sha256:ae1e57d3309a77e931df6e11419559df2cf5a82a9402bfb947900901b319c3e9` | half-open geographic partition; exceptions | retain |
| `coord-quarter-pose` | `sha256:0bfac14952b490ed6337fcd514c3572c5a0f3e58ee33dd251bc5a1c770c64eb8` | pose composition/inverse; modulo extrema | retain |
| `coord-isometric-diamond` | `sha256:0f1e20f69f1b994e83e34db4bfc9169a5dd9089ba3f140446d0cd93b873e1525` | sum/difference projection; parity inverse | retain |
| `coord-projective-rational` | `sha256:29f4ef6c4d7ea2e3a8fe492d65ca497bb97e00db91acfe58cea84e0287a34e3c` | homogeneous transform; gcd normalization | retain |
| `coord-octant-ring` | `sha256:fdb0d47d17a776547657f1255bb3e23def1bcb2c236f4b20a8bc053df7f8fd33` | unsigned signed-magnitude; boundary precedence | retain |
| `coord-cubemap-edge-step` | `sha256:6c23c355fd2f5ab2d2d45ddc5dafdf79c9c5d904a7702a30f4fb652f71cc948c` | validated enums; face-basis edge transition | retain |
| `coord-torus-nearest-delta` | `sha256:38241b5579127b3435b3ce1938a43fabd9fdb5aa87572bd7eee3a7950c681847` | centered modular delta; half-period tie | retain |
| `coord-voxel-axis-map` | `sha256:932ab6581fdfc6711e67ab0e7761556fcc39829c7ff1fffa1fee4d467db59bd4` | signed permutation; invalid-axis extrema | retain |
| `coord-tensor-stride` | `sha256:e74526a7d3e82df4cca6263e9b8abad22069444bacce9d06b5a5c2e87a61e90e` | mixed-radix strides; axis permutation | retain |
| `coord-ragged-linear` | `sha256:47b4f8e961fabd5b4668feddab554c957dff9d074acc62707f3fbc81f539a16c` | prefix index; empty-row inverse lookup | retain |
| `coord-upper-triangle-index` | `sha256:e0bdee0d001d490cbbaa22849914bc19b39a0688a5282318ef9e7faa2f65662b` | triangular rank/unrank; monotone search | retain |
| `coord-reflective-boundary-fold` | `sha256:73fe82eb0bffaf89d0936f3d0532f6b739cc8f608abd611a891d90660bd9cbbc` | triangle-wave fold; branch direction; replacement lineage | retain |
| `coord-camera-crop-orient` | `sha256:e13bab626f6ac537de32ae440785cc157bda7c86b0305c76401f40626507a273` | crop translation; rotate then mirror | retain |
| `coord-polyline-frame` | `sha256:4b3ec1c0c3e1a32ddf729494a3fec03e001bec930d0eb5db8e4da56fa1e4c73d` | full-input validation; orthogonal prefix selection; vertex handoff | retain |
| `coord-offset-hex-convert` | `sha256:4587354e3e008b8ed70fef957d1721fd5abd541587518e479439c6aeeb856fe4` | signed odd-row/cube conversion | retain |
| `coord-geofence-local` | `sha256:c22cdb364b29b4e504a329b67b60ee6f74305f3b23fd106827f67ede7edceaed` | dateline branch; checked rational scale | retain |
| `coord-integer-shear` | `sha256:d18148e53a71b11e04c3a1bdb0035c147eacb58d56d714b6c6039206d41e4fa6` | ordered unimodular updates; reverse inverse | retain |
| `coord-dihedral-canonical` | `sha256:ec0ba2b0e947e674ac91d7316b46ebccb7cbc9b0a8a95745cc3d08d0c71388b0` | D4 enumeration; normalized stable tie | retain |

Disposition counts: 25 `retain`, 0 `repair-and-reverify`, 0 `replace`, and
0 `reject` for this exact local-family subject.

## Structure, role, and prompt-boundary audit

- Exactly 25 unique task IDs and exactly 13 non-state files per root are
  present. Every path is a regular single-link file.
- Every config has two editable solution files, two hidden reference files,
  and visible/private tests. Role sets are nonempty, disjoint, relative, and
  resolve beneath the root.
- Independent prompt reconstruction found no `.meta/`, CMake, private-test,
  negative-source, example-source, or substantive reference-body leakage.
- Reconstructed prompts range from 2,454 to 3,015 bytes with a mean of
  2,698.32 bytes. All 25 prompt, instruction, and reference-source hashes are
  unique.
- Against the live 3,080 comparison roots there are zero candidate-ID, exact
  instruction, or exact reference-source collisions. Every provenance record
  declares clean-room `new-root` lineage, CC0-1.0, owner/spec binding, and the
  local-only nonclaim.
- Tokenizer measurement, assistant-loss masking, and training-context admission
  are inapplicable because no JSONL/SFT release is requested or produced.

## Runtime, correctness, and negative evidence

The bound creator receipt records three discovered and passing CTests per root
in both normal and fresh sanitizer builds, with every direct negative returning
nonzero. That is 150 recorded root CTest executions plus 50 recorded direct
negative executions over the two modes. Its three controls add 18 recorded
CTest executions and six recorded direct negative executions.

The independent audit did not rely on those statuses. It directly compiled the
raw `.meta/example.cpp` against `visible_test.cpp` and
`.meta/private_test.cpp`, and the raw `.meta/negative.cpp` against the private
test, using GCC 13.4.0 with `-Wall -Wextra -Wpedantic -Werror` and
`-fsanitize=address,undefined -fno-omit-frame-pointer` in the pinned no-network
image. All 50 reference executions exited zero; all 25 negative executions
exited nonzero. Static raw-reference review found no remaining unchecked signed
overflow, invalid-enum dispatch, premature partial return, or reference/private
role crossover.

The independent replacement-root harnesses add 270,901 axial-cell round trips,
two maximum-radius anchors, and 2,000,100 reflective-fold property cases. All
passed under ASan/UBSan. Independently recompiling and running each control's
visible, private, and negative programs added six passing control-reference
executions and three rejected control-negative executions.

## Diversity, adversarial controls, duplicates, and contamination

The diversity artifact contains all 300 unordered candidate pairs in all seven
required dimensions. Maximum retained-pair combined scores are below their
thresholds:

| Dimension | Maximum | Threshold |
| --- | ---: | ---: |
| public API | 0.776786 | 0.81 |
| owned state or algorithm | 0.723481 | 0.82 |
| mutation or selection rules | 0.486144 | 0.82 |
| invalid and boundary behavior | 0.821284 | 0.83 |
| reference control flow | 0.580421 | 0.82 |
| deterministic oracle | 0.788323 | 0.82 |
| topic-specific negative fixture | 0.629177 | 0.82 |

Independent byte comparison confirms that the domain/identifier,
constants/policy, and opposite-end controls change exactly the recorded 11, 3,
and 7 nonempty artifact sets. Each remains behaviorally coherent under the
fresh sanitizer executions and is detected as a clone in all seven dimensions.
The separate Morton/quadtree cross-alias control records the expected
`morton + interleav` mechanism marker and rejects the paired-bit digit-relabel
alias as `duplicate_family`.

The two superseded candidate roots are absent. The retained family has no exact
ID, prompt, instruction, reference, or root duplicates. Targeted live-corpus
searches found no foreign axial shell rank/unrank or reflective triangle-wave
fold. Shared vocabulary was classified by executable contract rather than
treated as automatic duplication.

The contamination receipt binds the final 3,080 comparison roots, all 26
official Aider C++ holdouts, and 77,650 comparisons. It reports maximum lexical
Jaccard 0.256579 and no benchmark or family overlap on the frozen inventory.
The final independently recomputed inventory is byte-semantically equal in
counts, sorted ID/path hashes, unique-ID set/hash, and reserved-lineage map, so
no comparison is stale at report freeze. No selected training manifest or
train/validation/test split exists or is authorized.

## Decision and limitations

Decision for exact subject
`sha256:566f9fcf3ca93f7724aa064a03e329a888dcfb82e7bfb691829ba59728296671`:
**`local_family_verified`**.

Confirmed: 25 exact raw roots, complete role separation, current inventory and
holdout binding, closure of CT-AUD-001 through CT-AUD-008, correctness and
novelty of both replacement roots, fresh direct reference/negative sanitizer
execution, full-input polyline suffix rejection, all-pairs diversity, and
executable adversarial controls.

This audit makes no JSONL, tokenizer/mask, split, dataset-release, producer or
consumer verification, training authorization, benchmark-uplift, or model-
quality claim. Any later owner, task, test, policy, comparison-inventory, or
environment change invalidates this exact-subject decision and requires a new
creator preflight and independent audit.
