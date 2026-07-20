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
- `docs/AIDER_SFT_SCOPE.md`

## Online Material Status

Online LFU-cache design exercises are useful for private concept study or
source discovery only. They are not a drop-in SFT source inventory: every
external source needs explicit license and semantic-contamination review.

The tasks below materialize as newly authored C++17 roots. Their interfaces,
tests, reference implementations, and provenance must be created in-repo and
pass the normal original-task admission process.

## Reverified v3 Replacement Tasks

| ID | Core mechanism | Distinguishing contract |
|---|---|---|
| `lfu-audio-waveforms-v3` | Weighted byte vector | Repeated victim scans clear a byte budget; one insertion can evict several entries. |
| `lfu-compiler-artifacts-v3` | Frequency-bucket index | A hash index and ordered LRU lists maintain key/bucket bijection. |
| `lfu-dns-answers-v3` | TTL heap then LFU | Generation-tagged expiry-heap records are swept before live selection. |
| `lfu-document-pages-v3` | Sliding access window | A bounded read-event deque is the authoritative frequency state. |
| `lfu-feature-config-v3` | Tenant vector ledgers | Each tenant owns an independent quota, clock, vector, and victim scan. |
| `lfu-image-transform-v3` | Rational cost index | An ordered score index is erased and reinserted on hit or repricing. |
| `lfu-package-manifests-v3` | Dependency graph | Cycle checks and reverse-edge traversal drive transitive invalidation. |
| `lfu-recommendations-v3` | Resident/ghost rings | Eviction transfers frequency into a bounded ghost history used on readmission. |
| `lfu-schema-metadata-v3` | Refresh-reset multimap | Refresh removes the old tuple index, resets frequency, and reinserts it. |
| `lfu-search-results-v3` | Lazy epoch decay | Rows normalize their counts lazily from their last recorded epoch. |
| `lfu-session-attributes-v3` | Lease partitions | Entries move between an evictable list and a token-owned leased partition. |
| `lfu-support-answers-v3` | Transactional snapshot vector | A complete temporary parse is validated before replacing a sorted live table. |
| `lfu-tax-estimates-v3` | LFUDA tournament tree | Bottom-up tournament winners select victims and propagate dynamic age. |
| `lfu-thumbnail-store-v3` | Count-min sketch admission | Three sketch rows gate admission into a second-chance resident ring. |
| `lfu-translation-memory-v3` | Validated event journal | Candidate batches are replayed completely before journal commit. |

Five legacy roots are intentionally rejected rather than counted through a
rename or small policy change:

| Legacy root | Rejection reason |
|---|---|
| `lfu-map-tiles` | Duplicates tenant-partitioned capacity and local victim selection. |
| `lfu-pricing-quotes` | Write-neutral behavior is only an update-policy toggle. |
| `lfu-product-catalog` | Duplicates the explicit frequency-bucket mechanism. |
| `lfu-route-planner` | Pinned exclusion duplicates lease-protected victim eligibility. |
| `lfu-weather-forecast` | Frequency capping is only a constant/overflow-policy toggle. |

## Materialization Requirements

The 15-count inventory is the minimum allowed by the remediation skill, not a
reason to retain weak tasks. Every v3 root differs in all seven hard-rule
dimensions: public API, owned state/algorithm, mutation and selection rules,
invalid/boundary behavior, reference control flow, deterministic oracle, and
executed topic-specific negative fixture. The owner checks each declared
dimension for uniqueness and separately measures normalized real docs, APIs,
reference control flow, and tests pairwise. A noun change, method rename,
constant, parameter, opposite-end choice, or overflow toggle is insufficient.

For each counted task, author a documented provenance record, starter
header/source pair, independent reference implementation, visible/private
tests, an independent complete-operation value trace, and a compiled false
substitute that the tests reject. Normal and fresh sanitizer builds run in the
repository-pinned network-disabled Docker sanity image; this evidence is
`docker_sanity`, not a family-designated locked oracle.

Across the family, hidden tests cover:

- capacity zero and capacity one;
- lookup and update frequency promotion;
- inserting a new key at full capacity evicting from the minimum-frequency
  bucket;
- least-recently-used tie-breaking among equal-frequency entries;
- removal of the last entry in a frequency bucket and correct minimum-frequency
  maintenance;
- replacing an existing value under the task-specific frequency policy;
- weighted multi-eviction, bucket migration, generation-safe TTL purge,
  access-window expiry, tenant isolation, cost ratios, dependency cycles and
  cascades, ghost re-admission, refresh reset, lazy decay, lease partitions,
  transactional checkpoints, LFUDA aging, sketch admission, and journal batch
  rollback;
- vector occupancy, key/bucket, graph-edge, score-index, partition-list,
  tournament-winner, sketch-ring, and journal-replay invariants;
- a task-specific deterministic value trace that calls every public operation
  class and checks the complete observable state after each operation.

The 20 legacy roots under `.w8-biayn/data/aider-tasks/aider-dsa/lfu-cache/`
remain immutable audit input. Regeneration targets only
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/lfu-cache/`.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
