# LRU Cache Curriculum: Topic 1, Subtask 9

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This subtask under **Linked Structure Invariants** teaches coherence between a
key-index map and a recency-ordered doubly linked list. Every successful
mutation must preserve both key lookup and least-recently-used eviction order.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

Online LRU-cache exercises, including direct design challenges, are useful for
private concept study or source discovery only. They are not a drop-in SFT
source inventory: every external source needs explicit license and semantic
contamination review.

The tasks below materialize as newly authored C++17 roots. Their interfaces,
tests, reference implementations, and provenance must be created in-repo and
pass the normal original-task admission process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `lru-thumbnail-cache` | Thumbnail cache | Store image previews, promote on view, and evict the least recently viewed preview. |
| `lru-web-page-cache` | Web-page cache | Cache page bodies by URL, update existing pages, and expose recency order. |
| `lru-session-store` | Session store | Read, refresh, revoke, and evict bounded user sessions. |
| `lru-dns-answer-cache` | DNS answer cache | Cache host answers, invalidate a host, and evict least-recently-resolved entries. |
| `lru-query-result-cache` | Query-result cache | Store database query results, replace results, and resize cache capacity. |
| `lru-compiler-artifacts` | Compiler-artifact cache | Cache object artifacts by build key and evict on bounded disk slots. |
| `lru-map-tile-cache` | Map-tile cache | Load, touch, remove, and evict geographic tile records. |
| `lru-product-details` | Product-detail cache | Cache product data, refresh a product, and enumerate most-recent items. |
| `lru-translation-cache` | Translation cache | Cache text-pair translations with normalized language-pair keys. |
| `lru-weather-snapshots` | Weather-snapshot cache | Add observations, lookup a location, and expire by logical timestamp plus recency. |
| `lru-document-pages` | Document-page cache | Keep recently opened document pages and evict when page-memory capacity is exceeded. |
| `lru-package-manifests` | Package-manifest cache | Resolve manifests, invalidate a package version, and preserve lookup consistency. |
| `lru-feature-config` | Feature-config cache | Cache tenant configurations, update values, and clear a tenant namespace. |
| `lru-tax-estimate-cache` | Tax-estimate cache | Cache estimates by request fingerprint and invalidate changed jurisdiction rules. |
| `lru-search-suggestions` | Search-suggestion cache | Cache normalized query suggestions and return recency-ranked cached queries. |
| `lru-audio-waveforms` | Audio-waveform cache | Store waveform chunks and evict by total byte budget rather than entry count. |
| `lru-route-plans` | Route-plan cache | Cache origin/destination plans, invalidate affected routes, and resize capacity. |
| `lru-recommendation-cache` | Recommendation cache | Cache user recommendations and remove entries for deleted users. |
| `lru-file-metadata` | File-metadata cache | Cache file metadata, update a file, and evict oldest untouched records. |
| `lru-pricing-quote-cache` | Pricing-quote cache | Cache quotes by request ID with explicit capacity-zero and overwrite semantics. |

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a textbook
`get(key)` / `put(key, value)` assignment as the visible contract. The key
normalization, eviction unit, invalidation behavior, update behavior, capacity
policy, and error cases must materially differ between roots.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- capacity zero and capacity one;
- cache hit promotion to most-recent position;
- updating an existing key without growing cache size;
- insertion at full capacity evicting exactly the least-recent key;
- removal or invalidation of the head, tail, and only entry;
- map/list bijection: every map entry occurs exactly once in the list and vice
  versa;
- sentinel/head/tail reciprocal links and forward/reverse recency agreement;
- byte-budget, logical-expiry, resize, or namespace semantics where applicable;
- long randomized operation sequences checked against a simple map plus
  recency-vector oracle.

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
