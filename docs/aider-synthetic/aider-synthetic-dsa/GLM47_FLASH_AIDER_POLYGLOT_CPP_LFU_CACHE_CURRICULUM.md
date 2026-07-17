# LFU Cache Curriculum: Topic 1, LFU Caches

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum teaches frequency-bucket and key-index coherence. On eviction,
the cache removes the least-frequently used entry; ties use the task-defined
least-recently-used order within the minimum-frequency bucket.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

Online LFU-cache design exercises are useful for private concept study or
source discovery only. They are not a drop-in SFT source inventory: every
external source needs explicit license and semantic-contamination review.

The tasks below materialize as newly authored C++17 roots. Their interfaces,
tests, reference implementations, and provenance must be created in-repo and
pass the normal original-task admission process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `lfu-product-catalog` | Product catalog cache | Cache product records and evict least-viewed products, breaking frequency ties by oldest access. |
| `lfu-search-results` | Search-result cache | Cache normalized query results and retain frequently revisited searches. |
| `lfu-translation-memory` | Translation-memory cache | Cache text translations and invalidate a changed language-pair namespace. |
| `lfu-dns-answers` | DNS-answer cache | Cache host resolutions, promote on lookup, and expire invalidated hosts. |
| `lfu-thumbnail-store` | Thumbnail store | Retain frequently viewed image previews under a bounded byte budget. |
| `lfu-weather-forecast` | Weather forecast cache | Cache location forecasts and apply logical expiry before frequency eviction. |
| `lfu-route-planner` | Route-plan cache | Retain frequently requested routes and clear routes touching a closed station. |
| `lfu-compiler-artifacts` | Compiler-artifact cache | Cache build artifacts and evict rarely reused artifacts under slot capacity. |
| `lfu-document-pages` | Document-page cache | Cache pages and report eviction diagnostics with frequency and recency. |
| `lfu-feature-config` | Feature-config cache | Cache tenant configuration reads and invalidate a tenant atomically. |
| `lfu-pricing-quotes` | Pricing-quote cache | Retain often requested quotes and replace quotes without resetting required policy state. |
| `lfu-recommendations` | Recommendation cache | Cache recommendations by user and remove entries for deleted accounts. |
| `lfu-map-tiles` | Map-tile cache | Keep frequently used map tiles and evict ties by oldest tile touch. |
| `lfu-package-manifests` | Package-manifest cache | Cache package metadata and invalidate a package version range. |
| `lfu-audio-waveforms` | Audio-waveform cache | Cache waveform chunks under a weighted capacity with deterministic LFU eviction. |
| `lfu-tax-estimates` | Tax-estimate cache | Cache estimates keyed by request fingerprint and reset affected jurisdiction entries. |
| `lfu-schema-metadata` | Schema-metadata cache | Cache table schemas and refresh a table without corrupting frequency buckets. |
| `lfu-session-attributes` | Session-attribute cache | Cache frequently read session attributes and revoke a full session namespace. |
| `lfu-image-transform` | Image-transform cache | Cache transformed images by source/options and evict low-use entries. |
| `lfu-support-answers` | Support-answer cache | Cache common support answers and provide a deterministic retained-key snapshot. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose only a
textbook `get(key)` / `put(key, value)` assignment. Key normalization,
frequency increment policy, tie-breaking, expiry/invalidation, capacity unit,
and diagnostic/query behavior must materially differ between roots.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- capacity zero and capacity one;
- lookup and update frequency promotion;
- inserting a new key at full capacity evicting from the minimum-frequency
  bucket;
- least-recently-used tie-breaking among equal-frequency entries;
- removal of the last entry in a frequency bucket and correct minimum-frequency
  maintenance;
- replacing an existing value under the task-specific frequency policy;
- expiration, namespace invalidation, byte-budget, or resize behavior where
  applicable;
- map/key-node, frequency-bucket, and recency-list bijections;
- long randomized operation sequences checked against a simple map plus
  frequency-and-recency oracle.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
