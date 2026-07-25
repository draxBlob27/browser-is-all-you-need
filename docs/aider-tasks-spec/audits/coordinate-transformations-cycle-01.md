# Coordinate Transformations Expansion: Independent Audit Cycle 01

Audit date: 2026-07-22
Audit subject: `.w8-biayn/data/aider-tasks-expansion-v1/text-grid/coordinate-transformations/`
Decision: **`not_completed`**

## Result first

The subject contains exactly 25 candidate roots and 325 non-state task files.
All 25 have structurally separated prompt, starter, reference, test, negative,
and metadata roles. The recorded Docker run reports three discovered and
passing CTests in both normal and fresh ASan/UBSan builds for every root and
all three adversarial controls. The generated family evaluator records all 300
unordered pairs in seven dimensions and rejects every control clone.

Those facts do not close the audit. Six hard-gate findings remain open:

- the frozen comparison inventory is stale by 60 expansion roots;
- `coord-morton-interleave` is a semantic duplicate of the already inventoried
  `basecv-morton-interleave-radix` root despite the generated contamination
  screen passing it;
- four references have independently reproduced boundary-contract defects:
  `coord-quarter-pose`, `coord-voxel-axis-map`,
  `coord-cubemap-edge-step`, and `coord-polyline-frame`.

Cycle 01 therefore retains 20 roots for regeneration-time review, requires
repair and re-verification of four roots, and requires replacement of one root.
No root is rejected irrecoverably, but zero roots are terminally admitted by
this report. A generator-owned regeneration and a new independent audit are
required; this report must remain immutable.

## Frozen subject and evidence

| Evidence | SHA-256 or value |
| --- | --- |
| Candidate tree, excluding `.state` by owner policy | `sha256:54932ece5c9b1810b278540e5784173851ed7f8d0797c501fc514a4a2b19d62b` |
| Owner | `sha256:e90aebe310f93e91e5c759822bfcd52179dbfebabc9d4014044c76316da5ecfe` |
| Curriculum | `sha256:f58249f9dc942c1923165bcece3299d68a7add0c62994ddfbbb324711744340a` |
| Family specification | `sha256:f3a42a07f566185412d502cd84c285b58c57c5370ff203aad7f7a393b058f965` |
| Focused tests | `sha256:73d91ffe90d880e76cf83cec28cead18793d9e0df0f291aa37e13f2a21e5cdf7` |
| Manifest bytes | `sha256:7fc95c5394664a64487e0893b5c8afa7b091ddb7568d42b1209f43ecedfb9db6` |
| Frozen source inventory bytes | `sha256:a3065dc04e1b976008f96063b7656926235cbc167856854686b2f674155967ee` |
| Diversity screen bytes | `sha256:26c26a4eea1ea4f9265c7c8a72049c29992c15b570b6cfec524f3bb95a04a955` |
| Contamination screen bytes | `sha256:0fc9c1b0d374d474d667a43a45c0c66fabef129527a88cf46cac5289e3a85467` |
| Docker-sanity receipt bytes | `sha256:5c034ed0ca8304f5efb2217680d1b09961d9cd8ddce1cbe7df57ec68bc7b1c41` |
| Creator-preflight receipt bytes | `sha256:8725794479ef7cc17c928ab9a2eb1623355edfedb6c9f6708f4a555d158dac45` |

The owner tree hash was independently recomputed and matched the manifest,
creator-preflight receipt, live-tree hash, and mounted-tree hash. The runtime
receipt binds image
`w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991`,
image ID of the same digest, network policy `none`, GCC 13.4.0 at
`/usr/local/bin/g++` with compiler hash
`sha256:152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`,
and CMake 3.25.1. This is repository Docker-sanity evidence, not a locked
family-specific oracle.

## Behavior contract used for audit

| Field | Contract |
| --- | --- |
| Task | Implement each declared C++17 coordinate transformation exactly. |
| Inputs | Only typed public API values; deterministic, offline, standard library only. |
| Output | Complete replacements for the declared header and source, with no other files or prose. |
| Invariants | Exact public API, atomic invalid return, checked arithmetic, documented orientation/order/tie policy, no private-role leakage. |
| Failure behavior | Invalid or unrepresentable inputs return the task's documented empty/false optional result without partial output or undefined behavior. |
| Resource limits | No network or third-party dependency; finite public domains where stated. No SFT token/context limit is authorized for this local family. |
| Evaluation | Visible/private/expected-failing-negative CTests in strict normal and fresh ASan/UBSan builds, plus independent boundary counterexamples and family/holdout screening. |
| Generalization target | Distinct coordinate systems and conventions, not renamed or policy-only variants of existing generated or benchmark tasks. |

## Stable findings

### CT-AUD-001 — blocker — frozen source inventory is no longer current

The frozen inventory records 731 generated roots, 709 reverify roots, and
1,595 foreign expansion roots, with 2,946 unique IDs and
`all_ids_hash=sha256:995e63ee40d85c0dbec5fddf24ab6e82e91764cbec39115ff5ce0e687208f37c`.
An independent read-only recomputation against the current trees found the
same 731 and 709 counts but 1,655 foreign expansion roots and 3,006 unique
IDs, with
`all_ids_hash=sha256:79c9e690be0c893def9dce9e8710cb16e1d522d81f09d01ddc78f08bc99e96f7`.

The 60-root change invalidates the artifact-bound no-collision/no-contamination
claim. It does not mutate the 25-root subject hash, but local-family completion
requires regeneration from the current inventory and a fresh screen.

Required remedy: regenerate from the owning source after the comparison trees
are stable, bind the new source inventory and all screens, and re-audit the
new exact tree.

### CT-AUD-002 — high — `coord-morton-interleave` duplicates an existing mechanism

The frozen inventory already contains
`.w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/base-conversion-invalid-digits/basecv-morton-interleave-radix`.
That root converts two coordinates into paired Morton quadrant digits and back;
its required mechanism is paired x/y-bit interleaving, and its forbidden
substitute concatenates all x bits then all y bits. `coord-morton-interleave`
implements the same paired x/y-bit interleave and inverse and rejects the same
concatenation substitute. Width (8 versus 16 bits), bit convention, and output
representation (base-4 digits versus a packed integer) do not add a distinct
primary mechanism under the user's no-semantic-duplicate boundary.

The production semantic-word screen scored this pair only about `0.2391`, well
below its `0.70` rejection threshold. Thus the passing contamination receipt
is a demonstrated false negative, not counterevidence.

Disposition: `replace-and-reverify`. Create a semantically new coordinate
transformation backfill; do not retain both as unrelated new roots. Strengthen
the comparison control so mechanism-equivalent representation/width variants
are caught.

### CT-AUD-003 — high — `coord-quarter-pose` has signed-int undefined behavior

The prompt requires Euclidean modulo-four headings for the complete `int`
domain. The reference computes
`a.quarter_turns + b.quarter_turns` before normalization and computes
`-p.quarter_turns` in inverse construction. `INT_MAX + 1` and `-INT_MIN` are
undefined signed overflow.

An independent compile against the exact reference in the pinned image with
ASan/UBSan called `compose_pose({{0,0},INT_MAX}, {{0,0},1})`. The mathematically
normalized heading is zero; execution instead exited 1 with UBSan reporting
signed overflow at `2147483647 + 1`.

Disposition: `repair-and-reverify`. Normalize operands before combining and
avoid negating an unnormalized `INT_MIN`; add normal and sanitizer private
tests for both extrema.

### CT-AUD-004 — high — `coord-voxel-axis-map` invokes `abs(INT_MIN)`

The contract says every axis code outside `-3..-1,1..3` is invalid and must be
rejected. The reference calls `std::abs(code)` before checking the allowed
range. For `code == INT_MIN`, that negation is unrepresentable.

An independent pinned-image ASan/UBSan run called
`remap_voxel({1,2,3}, {{INT_MIN,2,3}})` and exited 1 with UBSan reporting
negation of `-2147483648` in `std::abs`.

Disposition: `repair-and-reverify`. Range-check before absolute-value
conversion and add the exact invalid-code sanitizer case.

### CT-AUD-005 — high — `coord-cubemap-edge-step` accepts invalid enum values

The family specification explicitly requires invalid face and heading values
to reject. The reference validates size and cell coordinates but never
validates either enum. `basis` silently maps an unknown face to a zero basis,
and an unknown heading leaves `dr == dc == 0`.

An independent exact-reference executable supplied both
`static_cast<Face>(99)` and `static_cast<Heading>(99)` on otherwise valid
cells. At least one engaged optional was returned, and the discriminator exited
10 rather than zero.

Disposition: `repair-and-reverify`. Validate both enum domains before any
step, remove the silent fallback, and add direct private cases.

### CT-AUD-006 — high — `coord-polyline-frame` rejects a valid extreme endpoint

The contract accepts representable orthogonal segments and an in-range
`unsigned long long` distance. For the valid final segment
`{0,0} -> {LLONG_MIN,0}`, the length is `2^63`, which the distance type
represents. Sampling at distance `2^63` must return the final endpoint,
tangent `{-1,0}`, and segment zero.

The reference casts that distance to `long long`, then asks checked signed
multiplication to form `-1 * LLONG_MIN`; it returns failure. An independent
exact-reference executable asserted the documented endpoint and exited 10.

Disposition: `repair-and-reverify`. Handle the unsigned magnitude without an
out-of-range signed cast (including exact final endpoints), then add normal and
sanitizer tests at `2^63`.

## Root catalog and dispositions

Every row below was inspected from the raw prompt, header, reference, private
test, and negative source. `retain-pending-regeneration` is not admission: it
means no additional row-specific hard defect was confirmed in cycle 01, while
CT-AUD-001 still blocks the family.

| Root | Capability / tags | Cycle-01 disposition | Finding |
| --- | --- | --- | --- |
| `coord-affine-lattice` | checked arithmetic, affine map, overflow atomicity | retain-pending-regeneration | — |
| `coord-hex-cube-turn` | axial/cube invariant, cyclic orientation | retain-pending-regeneration | — |
| `coord-triangle-barycentric` | exact rational weights, degeneracy, divisibility | retain-pending-regeneration | — |
| `coord-viewport-letterbox` | rational scale, centered padding, pixel mapping | retain-pending-regeneration | — |
| `coord-tile-pyramid-address` | Euclidean division, signed cells, wrap | retain-pending-regeneration | — |
| `coord-morton-interleave` | bit interleave, encode/decode round trip | replace-and-reverify | CT-AUD-002 |
| `coord-hilbert-index` | locality curve, quadrant rotate/reflect, inverse | retain-pending-regeneration | — |
| `coord-utm-zone-band` | half-open geographic partition, named exceptions | retain-pending-regeneration | — |
| `coord-quarter-pose` | pose composition, inverse, modulo heading | repair-and-reverify | CT-AUD-003 |
| `coord-isometric-diamond` | sum/difference projection, parity inverse | retain-pending-regeneration | — |
| `coord-projective-rational` | homogeneous transform, gcd normalization | retain-pending-regeneration | — |
| `coord-octant-ring` | Chebyshev magnitude, boundary precedence | retain-pending-regeneration | — |
| `coord-cubemap-edge-step` | face bases, oriented edge transition | repair-and-reverify | CT-AUD-005 |
| `coord-torus-nearest-delta` | centered modular delta, half-period tie | retain-pending-regeneration | — |
| `coord-voxel-axis-map` | signed permutation, reflection, invalid axes | repair-and-reverify | CT-AUD-004 |
| `coord-tensor-stride` | mixed-radix strides, axis permutation, capacity | retain-pending-regeneration | — |
| `coord-ragged-linear` | prefix index, empty rows, inverse lookup | retain-pending-regeneration | — |
| `coord-upper-triangle-index` | triangular rank/unrank, monotone search | retain-pending-regeneration | — |
| `coord-quadtree-path` | paired bits, quadrant path, exact depth | retain-pending-regeneration | — |
| `coord-camera-crop-orient` | crop translation, rotate then mirror | retain-pending-regeneration | — |
| `coord-polyline-frame` | orthogonal prefix selection, vertex handoff | repair-and-reverify | CT-AUD-006 |
| `coord-offset-hex-convert` | odd-row/cube conversion, signed parity | retain-pending-regeneration | — |
| `coord-geofence-local` | dateline branch, rational local projection | retain-pending-regeneration | — |
| `coord-integer-shear` | ordered unimodular updates, reverse inverse | retain-pending-regeneration | — |
| `coord-dihedral-canonical` | D4 enumeration, normalization, stable tie | retain-pending-regeneration | — |

Disposition counts: 20 `retain-pending-regeneration`, 4
`repair-and-reverify`, 1 `replace-and-reverify`, 0 terminally admitted, and 0
irrecoverably rejected.

## Structure, role, and length audit

- Exactly 25 unique task IDs and exactly 13 non-state files per root were
  present.
- Each `.meta/config.json` names two editable solution files, two reference
  files, and visible/private tests. References, private tests, negative source,
  provenance, CMake, and receipts remain outside the built public prompt.
- Independent prompt reconstruction found zero occurrences of `.meta/`,
  `CMakeLists.txt`, private-test/negative paths, or the exact reference prefix.
- Public reconstructed prompt sizes range from 2,454 to 3,015 bytes, with a
  mean of 2,680 bytes. Reference C++ sources range from 618 to 1,755 bytes and
  private tests from 442 to 666 bytes.
- Tokenizer measurement and assistant-loss masking are not applicable: this is
  a local task family, not JSONL/SFT admission. No token or train-readiness
  claim is made.

## Runtime and negative-discriminator evidence

The recorded Docker receipt contains 25 root records and three control
records. Each record reports three tests in normal mode and the same three in
a fresh sanitizer build; all CTest runs pass and every direct negative
executable returns nonzero. This is 150 discovered root test executions plus
18 discovered control test executions, with 56 additional direct negative
executions across both modes.

This evidence proves only the checked cases. CT-AUD-003 through CT-AUD-006 are
valid deterministic counterexamples outside the generated private suite and
override the earlier pass for those roots. Several false substitutes also fail
early on broad invalid-input checks rather than uniquely isolating their named
subtle mechanism; remediation should add the new boundary cases without
weakening the existing compiled discriminator gate.

## Diversity and adversarial clone controls

The generated screen records 300/300 unordered candidate pairs, with all seven
dimensions present for every pair. Maximum retained-pair combined similarity
is below the configured threshold in every dimension. The three materialized
controls mutate nonempty artifact sets:

- domain/identifier rename: 11 changed files;
- constants/policy-only: 3 changed files;
- opposite-end selection: 7 changed files.

All three are rejected as clones in all seven dimensions and have normal plus
sanitizer runtime passage in the Docker receipt. The preliminary
`controls.json` and `diversity-screen.json` still label behavior execution as
pending even though `docker-sanity.json` records passage; the latter is the
stronger evidence, but regenerated state should converge those status fields.

The controls cover near-clones derived from one torus root. They do not cover
representation/width transformations of the same algorithm, which is exactly
the false-negative pattern in CT-AUD-002.

## Duplicate, lineage, and contamination report

- Within the 25-root subject: no duplicate ID, prompt hash, reference hash, or
  recorded seven-dimension pair failure was found.
- All 25 provenance records declare `lineage: new-root`, CC0-1.0, the same
  owner, curriculum, specification, and local-only nonclaim.
- Against the current comparison corpus: no exact candidate ID, corpus-text
  hash, or reference-source hash collision was found.
- A semantic mechanism collision was confirmed for `coord-morton-interleave`;
  see CT-AUD-002.
- The earlier screen covered all 26 official Aider C++ holdouts and reported
  no threshold violation. No hidden benchmark answer, test, or reference was
  found in a public prompt.
- Current split integrity is not applicable. No train, validation, test, or
  selected manifest exists or is authorized for this family.

## Corpus composition

The family covers checked continuous/discrete transforms, orientation groups,
spatial curves, mixed-radix and ragged indexing, geographic conventions,
topological face transitions, and canonicalization. Interaction mode is
single-task whole-file editing; all sources are synthetic clean-room new-root
candidates; all oracles are deterministic C++ executables. Every task uses the
same compact file skeleton and strict build policy, while the public APIs and
primary mechanisms differ except for the external Morton collision.

The corpus is therefore broad by coordinate mechanism but monocultural by
authoring source and interaction format. That is acceptable for a local
curriculum family and is not evidence of dataset balance or training value.

## Required remediation and next gate

1. Preserve this report and stable finding IDs unchanged.
2. Record owner-level remedy decisions for CT-AUD-001 through CT-AUD-006.
3. Replace `coord-morton-interleave` with a semantically new backfill; do not
   rename or lightly vary the collided mechanism.
4. Repair the four boundary defects and add exact normal/sanitizer regressions.
5. Strengthen external semantic-clone screening for representation/width
   variants, then regenerate all 25 roots from the owner against the current
   source inventory.
6. Rerun focused tests, core verification, all 300 pair decisions, all three
   controls, current contamination/holdout screens, and pinned Docker normal
   plus fresh sanitizer evidence.
7. Perform a fresh independent audit against the post-remediation tree and
   new evidence hashes.

The strongest truthful terminal status for cycle 01 is `not_completed`.
`local_family_verified`, dataset release, SFT row readiness, training
authorization, and benchmark uplift are not claimed.
