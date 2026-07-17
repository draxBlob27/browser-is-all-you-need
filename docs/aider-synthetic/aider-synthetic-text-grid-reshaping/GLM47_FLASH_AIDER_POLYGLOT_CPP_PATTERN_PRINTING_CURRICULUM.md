# Pattern Printing Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops rule-derived symmetric rendering, width arithmetic,
symbol policies, and observable whitespace control without recreating a bare
diamond-printing exercise.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

`diamond` and every other official Aider Polyglot C++ root are permanent
holdouts. Do not reuse their text, APIs, examples, tests, references, or
distinctive behavior. Each proposal needs a domain result beyond a shape string
and materially different symbols, constraints, alignment, and validation.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `pattern-theater-seating` | Theater seating chart | Render tiered seat bands and return vacant totals. |
| `pattern-ski-trail-sign` | Ski trail sign | Produce a centered difficulty marker with a legend. |
| `pattern-roof-trusses` | Roof trusses | Render triangular truss levels and validate load labels. |
| `pattern-festival-bunting` | Festival bunting | Generate pennant rows with exact edge tassels. |
| `pattern-orchard-canopy` | Orchard canopy | Render a symmetric canopy and count fruit markers. |
| `pattern-signal-cones` | Signal cones | Produce warning-cone rows with a stripe cadence. |
| `pattern-tournament-bracket` | Tournament bracket | Render seed tiers with declared bye positions. |
| `pattern-mountain-profile` | Mountain profile | Draw joined peaks and reject illegal ridge overlaps. |
| `pattern-lighthouse-beam` | Lighthouse beam | Render expanding beam frames with a fixed tower. |
| `pattern-quilt-medallion` | Quilt medallion | Generate concentric bands and report color counts. |
| `pattern-pyramid-crates` | Pyramid crates | Render stacked labels with multi-digit alignment. |
| `pattern-garden-trellis` | Garden trellis | Draw mirrored vines while preserving blocked cells. |
| `pattern-snowflake-banner` | Snowflake banner | Render a six-arm motif with a caller center token. |
| `pattern-archway-stones` | Archway stones | Produce an arch and validate keystone location. |
| `pattern-warehouse-stacks` | Warehouse stacks | Render stock columns and capacity markers. |
| `pattern-launch-countdown` | Launch countdown | Draw descending numeral triangles at fixed width. |
| `pattern-choir-riser` | Choir riser | Render riser positions and voice-part markers. |
| `pattern-harbor-beacons` | Harbor beacons | Produce mirrored beacon flashes around a channel. |
| `pattern-ice-rink-lines` | Ice rink lines | Render a symmetric center-line motif. |
| `pattern-cave-supports` | Cave supports | Draw tapered braces and report material quantities. |

## Materialization Requirements

Use domain records and return a rendering plus an aggregate or diagnostic, not
`make_diamond`. Hidden tests cover zero/one dimensions, odd/even policy,
custom symbols, multi-character labels, line width, blank cells, trailing
spaces, final newline, invalid parameters, and an independent row invariant.

## Admission Boundary

Original C++17 APIs, provenance, reference/hidden Catch tests, normal and
sanitizer proof, contamination/family review, and all release gates are mandatory.
