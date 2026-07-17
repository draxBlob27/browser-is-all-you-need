# ASCII Art Scaling Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops nearest-neighbor character-grid scaling, shape
preservation, palette/blank-cell rules, dimensions, and output diagnostics.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

All official Aider holdouts are excluded. Do not author a generic text-image
resizer alone. Each candidate must use a domain format, explicit scale policy,
and a distinct validation/aggregate result; holdout and semantic screens block
near-matches.

## Proposed Decontaminated Tasks

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

## Admission Boundary

Every candidate remains subject to original C++17 assets, provenance, oracle
and sanitizer proof, contamination/family screening, renderer/token evidence,
and immutable-release verification.
