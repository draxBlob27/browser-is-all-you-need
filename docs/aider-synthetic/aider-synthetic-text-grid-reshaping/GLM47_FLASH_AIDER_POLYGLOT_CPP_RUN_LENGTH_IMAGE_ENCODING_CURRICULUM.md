# Run-Length Image Encoding Curriculum: Decontaminated Capability

Status: curriculum-design note. These original concepts are not admitted SFT roots.

This curriculum develops row-bounded image runs, canonical encoding/decoding,
count validation, and image-specific aggregates without a generic string codec.

Use this with `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_TEXT_AND_GRID_RESHAPING_TOPICS.md` and `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`.

## Decontamination Boundary

All official holdouts and existing excluded run-length source families are
permanent exclusions. Do not reuse their artifacts. Candidates must differ in
2D row boundaries, pixel model, record format, query, and validation policy.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `image-rle-farm-map` | Farm map | Encode crop rows and calculate planted area by crop. |
| `image-rle-weather-radar` | Weather radar | Decode reflectivity runs and find storm columns. |
| `image-rle-security-mask` | Security mask | Encode motion masks and validate frame dimensions. |
| `image-rle-warehouse-plan` | Warehouse plan | Decode aisle maps and count accessible cells. |
| `image-rle-medical-scan` | Medical scan | Encode tissue classes and report lesion bounding boxes. |
| `image-rle-satellite-clouds` | Satellite clouds | Decode cloud masks and compute clear-pixel ratio. |
| `image-rle-quilt-pattern` | Quilt pattern | Canonicalize color runs and count seam transitions. |
| `image-rle-floor-mosaic` | Floor mosaic | Encode tile colors and reject inconsistent row widths. |
| `image-rle-orchard-drone` | Orchard drone | Store canopy masks and total healthy-tree pixels. |
| `image-rle-fire-map` | Fire map | Decode hazard bands and report border hotspots. |
| `image-rle-seat-chart` | Seat chart | Encode vacant/occupied rows and find largest vacancy run. |
| `image-rle-coral-survey` | Coral survey | Compress coral classes and return class histograms. |
| `image-rle-paint-inspection` | Paint inspection | Decode defect pixels and find affected panels. |
| `image-rle-snow-cover` | Snow cover | Encode coverage cells and compare two map areas. |
| `image-rle-traffic-camera` | Traffic camera | Compress lane masks and count blocked lanes. |
| `image-rle-library-shelves` | Library shelves | Encode shelf occupancy and find empty stretches. |
| `image-rle-circuit-layout` | Circuit layout | Decode conductive rows and validate pad positions. |
| `image-rle-garden-irrigation` | Garden irrigation | Encode wet cells and calculate dry-bed spans. |
| `image-rle-game-sprite` | Game sprite | Decode a palette sprite and verify transparent borders. |
| `image-rle-harbor-depth` | Harbor depth | Compress depth bands and calculate safe-channel pixels. |

## Materialization Requirements

Define row boundaries, palette/default rules, count type, and malformed-record
policy. Hidden tests cover empty/singleton rows, counts at limits, adjacent
mergeable runs, truncated/zero/overflow counts, exact width, encode/decode
round trips, canonical form, and a dense-image oracle.

## Admission Boundary

Every candidate requires original C++17 assets, provenance, oracle/sanitizer,
contamination and family isolation, renderer/token evidence, and release proof.
