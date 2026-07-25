# Coordinate Transformations Expansion Curriculum

Status: executable clean-room curriculum for 25 local candidate roots. This
document implements only the `Grid coordinate transforms, orientation, and
traversal` count cell in
`docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md`. It creates no
SFT rows, dataset release, training authorization, or benchmark-uplift claim.

## Evidence and boundary

The weakness target is first-try implementation of coordinate conventions,
orientation changes, invertible addressing, checked arithmetic, and boundary
rules. The permanent 26-root Aider Polyglot C++ benchmark is a holdout. The
existing generated and reverify trees, including matrix rotation, transpose,
sparse encoding, ASCII scaling, maze, flood-fill, and grid-ownership roots,
are reserved semantic lineages. New roots are written only beneath
`.w8-biayn/data/aider-tasks-expansion-v1/text-grid/coordinate-transformations/`.

Every root is newly repository-authored under CC0-1.0. Its public prompt shows
only the two documentation files and its declared header/source starter pair.
References, tests, CMake, provenance, screens, controls, and receipts stay
private. All arithmetic and ordering rules are deterministic and C++17.

## Binding 25-root inventory

| Task ID | Public capability | Substantive mechanism | Invalid, boundary, ordering, and tie contract | Compiling false substitute rejected by private tests |
| --- | --- | --- | --- | --- |
| `coord-affine-lattice` | Apply a checked 2-D affine lattice map | six-coefficient checked multiply/add | reject overflow; preserve signed coordinates | unchecked arithmetic with wrapped results |
| `coord-hex-cube-turn` | Rotate axial hex coordinates in sixty-degree steps | axial-to-cube invariant and repeated cube rotation | Euclidean-normalize turns; cube sum stays zero | rotate as a square-grid quarter turn |
| `coord-triangle-barycentric` | Map exact barycentric weights into a triangle | determinant-aware integer numerator evaluation | reject degenerate triangles and weights not summing to the denominator | average vertices and ignore weights |
| `coord-viewport-letterbox` | Map source pixels into an aspect-preserving viewport | rational scale comparison plus centered padding | reject empty rectangles/out-of-range pixels; left/top tie owns the spare pixel | independently scale x and y |
| `coord-tile-pyramid-address` | Split signed world cells into wrapped tiles and local cells | Euclidean floor division and horizontal modulus | positive extent only; negative inputs retain non-negative locals | C++ truncating division/remainder |
| `coord-hex-ring-address` | Rank/unrank cells in a bounded axial hexagon | six-direction axial shell walk with checked ring prefixes | radius at most one million; center is rank zero; reject cells outside the hexagon | bounding-square row-major rank includes non-hex cells |
| `coord-hilbert-index` | Convert between square-grid points and Hilbert distance | iterative quadrant rotation/reflection | order 1..10; reject out-of-range coordinates and distances | row-major indexing |
| `coord-utm-zone-band` | Classify longitude/latitude microdegrees into a deterministic zone/band cell | half-open range partition with Norway/Svalbard exceptions | longitude +180 belongs to zone 60; invalid latitude rejected | plain six-degree division without exceptions |
| `coord-quarter-pose` | Compose and invert integer poses with quarter-turn headings | semidirect-product pose composition | headings normalized modulo four; inverse is exact | add translations without rotating the child frame |
| `coord-isometric-diamond` | Project and exactly unproject tile coordinates | sum/difference transform with parity validation | inverse rejects odd half-coordinates | integer-divide invalid parity points |
| `coord-projective-rational` | Apply an integer homogeneous projective transform | checked dot products and gcd-normalized rational output | reject zero denominator and overflow; denominator canonical positive | discard the homogeneous denominator |
| `coord-octant-ring` | Classify integer points by Chebyshev ring and directed octant | magnitude comparison with axis precedence | origin is its own class; clockwise boundary ties are explicit | floating `atan2` sector rounding |
| `coord-cubemap-edge-step` | Step across oriented cube-face edges | face-local basis vectors and normal/basis remapping | reject invalid face/cell/heading; edge transitions preserve cell offset | wrap on the same face |
| `coord-torus-nearest-delta` | Compute deterministic shortest displacement on a torus | centered modular reduction per axis | positive half-period wins exact even-period ties | raw subtraction without wrapping |
| `coord-voxel-axis-map` | Apply a validated signed 3-D axis permutation | bijective signed-axis lookup | reject repeated/zero/out-of-range axes and overflow | ignore axis signs |
| `coord-tensor-stride` | Linearize and unlinearize coordinates under an axis order | checked mixed-radix strides | positive ranks/extents; permutation required; reject capacity overflow | always use row-major order |
| `coord-ragged-linear` | Map ragged row coordinates to/from a flat index | checked prefix-length accumulation | empty rows allowed; invalid row/column/index rejected | multiply row by maximum width |
| `coord-upper-triangle-index` | Rank/unrank upper-triangle coordinates | triangular prefix counts and monotone search | require row <= column and bounded size; exact inverse | dense square row-major index |
| `coord-reflective-boundary-fold` | Fold unbounded signed coordinates into a bounded reflective box | Euclidean triangle-wave phase with branch direction | extents 1..1,000,000,000; singleton axes return zero direction; exact signed extrema | clamp coordinates to the nearest boundary |
| `coord-camera-crop-orient` | Map sensor pixels through crop, quarter-turn, and mirror | crop translation followed by dimension-aware orientation | reject outside crop; mirror applies after rotation | mirror before rotating with source dimensions |
| `coord-polyline-frame` | Locate an integer-distance sample on an orthogonal polyline | checked segment-prefix selection and signed unit direction | reject diagonal/zero-length segments and distances past the end; vertex ties select next segment | interpolate using only endpoints |
| `coord-offset-hex-convert` | Convert odd-row offset hex cells to cube and back | parity-correct floor-half conversion | signed rows supported; cube invariant required | use truncating `row / 2` for negative odd rows |
| `coord-geofence-local` | Convert microdegree fixes to a local tangent integer frame | dateline-aware longitude delta and latitude-scaled rational projection | reject invalid fixes/scale; shortest dateline branch wins | subtract longitude without dateline wrapping |
| `coord-integer-shear` | Apply and invert a sequence of checked integer shears | unimodular elementary transforms in declared order | reject invalid axis codes and overflow; inverse walks operations backward | apply inverse operations in forward order |
| `coord-dihedral-canonical` | Canonicalize a finite point shape under all eight square symmetries | enumerate, origin-normalize, sort, and lexicographically select D4 images | reject duplicate input points; empty shape is canonical empty; ties use transform order | inspect rotations only and omit reflections |

## Executable family contract

Before reference authoring, each row above fixes its namespace-level C++17 API,
owned algorithm, failure policy, deterministic tie/order behavior, reference
oracle, and one coherent bad implementation. The normative declarations,
examples, per-root test names, exact file roles, and acceptance commands are in
`docs/aider-tasks-spec/aider-text-grid-reshaping/coordinate-transformations-expansion.md`.
The generator must refuse every output except the exact expansion family root,
reject symlink/hardlink escape, and reject any ID or semantic-lineage overlap
with either existing generated tree or another expansion family.

The family diversity gate compares all 300 unordered pairs over these seven
separate artifact-derived dimensions: public API, owned state/algorithm,
mutation/selection rules, invalid/boundary behavior, reference control flow,
deterministic oracle, and topic-specific negative fixture. One aggregate score
cannot compensate for a duplicated dimension. Coherent domain/identifier,
constants/policy-only, and opposite-end controls are materialized from an
emitted root, must change files, must build and pass their internally coherent
behavior tests in normal and fresh sanitizer configurations, and must then be
rejected as clones by the same production evaluator. A separate cross-alias
control must equate Morton/interleaved paired-bit radix language with
quadtree/quadrant-path language despite digit relabeling, width, or storage
representation changes.

## Verification and non-claims

Creator preflight requires exact regeneration, prompt/role/reference mapping,
25 roots, 300 seven-dimension pair decisions, all three coherent emitted clone
controls plus the Morton/quadtree cross-alias control, 25 compiled/executed
false substitutes, a complete existing-tree and
26-holdout contamination screen, and equal positive normal/fresh ASan/UBSan
test discovery in the pinned network-disabled repository sanity image. A
read-only independent audit then owns disposition. Any finding routes through
owner-controlled remediation and complete regeneration before a fresh audit.
Only that fresh audit may conclude `local_family_verified`.

No JSONL, split, token/mask artifact, release, training run, or uplift claim is
authorized by this curriculum.
