# ASCII Art Scaling Curriculum: Decontaminated Capability

Status: v2 `local_family_verified`. The legacy generated family is preserved as
audit input and is not admitted SFT material.

This curriculum develops nearest-neighbor character-grid scaling, shape
preservation, palette/blank-cell rules, dimensions, and output diagnostics.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/AIDER_SFT_SCOPE.md`.

## Decontamination Boundary

All official Aider holdouts are excluded. Do not author a generic text-image
resizer alone. Each candidate must use a domain format, explicit scale policy,
and a distinct validation/aggregate result; holdout and semantic screens block
near-matches.

## Legacy V1 Audit

The 20 legacy roots are one semantic template: a rectangular nearest-neighbor
scaler returning the same `rows`/`marked_cells`/`valid` report. Class, domain,
and marker substitutions are the only differences, and the visible/private
tests repeat one two-cell example. Finding `ASCII-SCALE-001` therefore records
that the primary objective is not independently achieved by 20 roots;
`ASCII-SCALE-002` records template-family duplication; and `ASCII-SCALE-003`
records insufficient prompt, boundary, and negative-fixture evidence.

The deterministic disposition keeps the lexicographically smallest
independently justified representative, `scale-archive-stamps`, as
`repair-in-place`. The other 19 legacy roots are `replace`; no rename-only root
is retained. Per-root frozen records and specifications live under the parallel
reverify family's `.state/remedy/` directory.

## Legacy V1 Inventory

| ID | Task | Visible contract |
|---|---|---|
| `scale-weather-symbols` | Weather symbols | Scale forecast icons and preserve transparent cells. |
| `scale-evacuation-signs` | Evacuation signs | Enlarge exit maps and report blocked-arrow pixels. |
| `scale-garden-plans` | Garden plans | Resize planting diagrams and count crop-cell area. |
| `scale-warehouse-labels` | Warehouse labels | Magnify bin maps and retain aisle separators. |
| `scale-quilt-preview` | Quilt preview | Scale patch artwork and calculate palette totals. |
| `scale-ski-trail-map` | Ski trail map | Enlarge trail diagrams and preserve lift symbols. |
| `scale-circuit-icons` | Circuit icons | Resize component art and validate connector positions. |
| `scale-museum-wayfinding` | Museum wayfinding | Scale gallery signs and retain door markers. |
| `scale-orchard-layout` | Orchard layout | Magnify tree maps and count irrigation cells. |
| `scale-radar-glyphs` | Radar glyphs | Resize contact glyphs and retain center markers. |
| `scale-theater-backdrop` | Theater backdrop | Scale scenery art and report painted area. |
| `scale-cave-warning` | Cave warning | Enlarge hazard signs and preserve border thickness. |
| `scale-factory-status` | Factory status | Scale status panels and count alert pixels. |
| `scale-harbor-flags` | Harbor flags | Resize signal flags and verify stripe order. |
| `scale-lab-plate-map` | Lab plate map | Magnify well diagrams and preserve sample labels. |
| `scale-solar-dashboard` | Solar dashboard | Scale panel states and calculate shaded area. |
| `scale-school-seating` | School seating | Enlarge seating charts and retain aisle columns. |
| `scale-flood-warning` | Flood warning | Resize flood maps and count evacuation marks. |
| `scale-archive-stamps` | Archive stamps | Magnify stamp art and keep margin whitespace. |
| `scale-game-minimap` | Game minimap | Scale terrain grid and report visible tile counts. |

## Materialization Requirements

Specify integer scale factors, empty/ragged input policy, blank/palette rules,
and output-width behavior. Hidden tests cover factor one, horizontal/vertical
factors, invalid/zero factors, blank rows, multi-symbol cells if supported,
exact dimensions, and an independent repeated-cell oracle.

## V2 Replacement Inventory

The owner materializes exactly these behaviorally and algorithmically distinct
local roots beneath the parallel reverify tree. The count preserves audit
accounting for all 20 legacy roots; it is not a dataset quota.

| V2 task ID | Primary mechanism |
| --- | --- |
| `scale-archive-stamps` | Nearest-neighbor enlargement with an unscaled whitespace margin. |
| `nine-slice-cave-frame` | Corner-preserving nine-slice frame stretching. |
| `connector-grid-dilation` | Manhattan-radius connector dilation with row-major change diagnostics. |
| `route-map-aspect-fit` | Largest integer aspect fit centered in a fixed box. |
| `status-panel-decimator` | Phase-zero row/column stride decimation. |
| `flood-map-majority-downsample` | Complete-block strict-majority reduction with explicit ties. |
| `minimap-viewport-zoom` | Bounded center/radius crop followed by integer zoom. |
| `garden-tile-repeat` | Whole-pattern two-dimensional tiling. |
| `flag-stripe-resampler` | Largest-remainder proportional stripe allocation. |
| `plate-coordinate-expander` | Sparse labeled-coordinate to dense square-well expansion. |
| `wayfinding-letterbox` | Centered padding without resampling. |
| `orchard-sparse-expander` | Ordered irrigation row/column band insertion. |
| `quilt-block-magnifier` | One-character token block rasterization with palette totals. |
| `radar-center-anchored-scale` | Symmetric radar resampling with Chebyshev-ring counts. |
| `seating-aisle-preserving-scale` | Selective seat scaling that retains unit-width aisles. |
| `trail-polyline-raster-scale` | Orthogonal polyline coordinate scaling and rasterization. |
| `solar-palette-quantizer` | Horizontal area-bucket resampling over ordered palette indices. |
| `backdrop-layer-compositor` | Transparent ordered compositing followed by scaling. |
| `label-runlength-expander` | Run-length decoding fused with anisotropic expansion. |
| `weather-frame-atlas-scale` | Equal-frame scaling and fixed-gutter atlas assembly. |

The focused owner screen derives role-prefixed lexical shingles from emitted
docs, APIs, references, visible tests, and private tests after removing
identifiers, literals, clean-room domain nouns, and endpoint direction. It
compares all 190 unordered family pairs; rejects full copied-root
domain/identifier, constants/policy-only, and opposite-selection clone
controls through the same decision; and compares every emitted root against
all 26 bound official Aider C++ holdouts. Unique IDs, profile labels, and raw
hash inequality are not diversity evidence.

## Reverification Evidence

Changed owners are
`src/w8_biayn/integrations/moonlight_ascii_art_scaling_aider_tasks.py`,
`src/w8_biayn/integrations/moonlight_ascii_art_scaling_cases.py`, the focused
pytest, wrapper, this curriculum, materialization guide, and audit report. Full
per-root before/after tree hashes and remedy-spec hashes are bound in the 20
`.state/remedy/*.json` records.

The owner revision is
`sha256:7b73f3607ee79e1f0412a1460b2ce3b3729d1c3bc7d2a1cdd1e5dfad324335a1`.
Host verification is truthfully `not_completed` because host CMake is absent.
The mandatory network-disabled Docker sanity receipt binds archive hash
`sha256:c43e028f3d17f0c08ddf12f1d8bad4c520418095edc39836fa4dba1e9e230d56`
to the pinned image. All 20 roots pass three normal and three fresh ASan/UBSan
tests with matching counts. Twenty distinct false substitutes compile under
the exact strict flags, then all 40 direct normal/sanitizer executions return
exactly 1 with no diagnostics. Docker independently computes the exact owner
tree digest for every mounted root; 20/20 match and the current owner imports
the direct result only after live reconciliation. Prompt/role, 190-pair
family, and 520-comparison benchmark screens pass. The evidence class is
`docker_sanity`, with `locked_oracle: false`.

## Admission Boundary

Every candidate remains subject to C++17 provenance, prompt/role boundaries,
normal and fresh ASan/UBSan Docker sanity, executed false-substitute fixtures,
and contamination/family screening. Renderer/token evidence and immutable
release verification are not requested by this local remediation and must not
be inferred from `local_family_verified`.
