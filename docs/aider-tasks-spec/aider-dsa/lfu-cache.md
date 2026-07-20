# LFU Cache Reverification Audit

## Scope and correction

This audit covers all 20 legacy roots under
`.w8-biayn/data/aider-tasks/aider-dsa/lfu-cache/` using the mandatory prompt
`docs/aider-tasks-spec/prompts/remediate-family-reverify.md`. The legacy tree
remained unchanged. The parallel reverify tree contains 15 v3 replacements;
five legacy proposals are rejected because counting them would violate the
skill's hard logic-and-implementation diversity rule.

The earlier v2 report is withdrawn. It incorrectly treated unique mode names,
source markers, and hashes containing those names as diversity proof. It also
used one superset header/state template, one mostly shared victim-selection
body, non-executed negative markers, and a generic trace that omitted
profile-specific operations. Those findings forced every prior v2 root back to
`planned`; the v2 generated roots and stale receipt were removed only through
the owner during v3 regeneration.

This remains local task-family evidence. It creates no SFT rows, release,
training authorization, or benchmark result.

## Hard-rule design and enforcement

Every counted v3 root differs in the seven required dimensions:

1. public API;
2. owned state or substantive algorithm;
3. mutation and selection rules;
4. invalid and boundary behavior;
5. reference control flow;
6. deterministic complete-operation value oracle; and
7. topic-specific compiled false substitute.

The focused test requires every dimension to have 15 unique values. The owner
then normalizes the actual generated docs, header API, reference, visible test,
hidden test, and independent oracle test and compares every candidate pair.
Names, comments, strings, literals, and domain identifiers do not establish a
pass. Each `.meta/negative.cpp` builds against the same header and tests; a
negative fixture passes only when CTest executes and rejects it.

## Commands and results

- `UV_CACHE_DIR=/tmp/lfu-v3-uv-cache uv run pytest -q tests/test_moonlight_lfu_cache_aider_tasks.py`: `5 passed`.
- Targeted Ruff over the owner, cases, and focused test: passed.
- `python3 -m w8_biayn.integrations.moonlight_lfu_cache_aider_tasks --out .w8-biayn/data/aider-tasks-reverify/aider-dsa/lfu-cache --force --verify-core --verify`: wrote 15 v3 tasks, retained five rejection records, and passed.
- Docker sanity image: `w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991` with `--network none`.
- Runtime: GCC 13.4.0 at `/usr/local/bin/g++`, compiler SHA-256 `152d9e7fc46bb71081e0d962714f7235c21eeec596a0daef7d40a220e7ebf663`, CMake 3.25.1.
- Every counted root discovered and passed three normal tests and three fresh ASan/UBSan tests. Every deliberate substitute discovered three tests and all three failed as required.
- Receipt ID: `sha256:d1d39f6043fd9055a5fbe4cf6b889c0ae5ee06fcdd06a01de9bfff1577054d02`.
- Strongest normalized family pair: `lfu-audio-waveforms-v3` / `lfu-recommendations-v3`, Jaccard `0.599201`, below the blocking `0.76` threshold.
- All 26 official Aider C++ roots were bound. Strongest candidate/holdout pair: `lfu-tax-estimates-v3` / `crypto-square`, Jaccard `0.146319`, below `0.68`.

The receipt labels this evidence `docker_sanity`. This family does not name a
designated locked grader, so the result is not described as `locked_oracle`.
It binds the deterministic archive, host and independently mounted task hashes,
owner hashes, reference hashes, immutable image, compiler identity and hash,
CMake version, exact verifier script and Docker command, normal/sanitizer
counts, negative failures, and network policy.

## Per-root dispositions

| Legacy root | v3 result | Core implementation | Tree hash prefix | Disposition/status |
|---|---|---|---|---|
| `lfu-audio-waveforms` | `lfu-audio-waveforms-v3` | weighted byte vector with repeated eviction | `d2d7ae3b7d31` | replace / `local_family_verified` |
| `lfu-compiler-artifacts` | `lfu-compiler-artifacts-v3` | hash index plus ordered frequency lists | `060345eaea82` | replace / `local_family_verified` |
| `lfu-dns-answers` | `lfu-dns-answers-v3` | generation-tagged expiry heap before LFU | `8fdc0caa9fda` | replace / `local_family_verified` |
| `lfu-document-pages` | `lfu-document-pages-v3` | sliding access-event deque | `c7c9fa38b0fd` | replace / `local_family_verified` |
| `lfu-feature-config` | `lfu-feature-config-v3` | independent per-tenant vector ledgers | `25a7d03b92ed` | replace / `local_family_verified` |
| `lfu-image-transform` | `lfu-image-transform-v3` | ordered recomputation-ratio index | `9fe4080eea93` | replace / `local_family_verified` |
| `lfu-package-manifests` | `lfu-package-manifests-v3` | cycle-checked dependency graph and cascade | `efff80a4d175` | replace / `local_family_verified` |
| `lfu-recommendations` | `lfu-recommendations-v3` | resident vector plus bounded ghost ring | `a5bf1128460f` | replace / `local_family_verified` |
| `lfu-schema-metadata` | `lfu-schema-metadata-v3` | refresh-reset tuple multimap | `d162c7acc54f` | replace / `local_family_verified` |
| `lfu-search-results` | `lfu-search-results-v3` | lazy per-row epoch decay | `b2c2b7016f1c` | replace / `local_family_verified` |
| `lfu-session-attributes` | `lfu-session-attributes-v3` | leased and evictable partitions | `7e53d0232e7b` | replace / `local_family_verified` |
| `lfu-support-answers` | `lfu-support-answers-v3` | transactional sorted-vector snapshot restore | `052299348918` | replace / `local_family_verified` |
| `lfu-tax-estimates` | `lfu-tax-estimates-v3` | LFUDA tournament tree | `ace91ea557f0` | replace / `local_family_verified` |
| `lfu-thumbnail-store` | `lfu-thumbnail-store-v3` | count-min sketch plus second-chance ring | `6a82d17fd26b` | replace / `local_family_verified` |
| `lfu-translation-memory` | `lfu-translation-memory-v3` | validated event journal replay | `9940d765e693` | replace / `local_family_verified` |
| `lfu-map-tiles` | none | duplicates tenant-local partitioning | n/a | reject / `rejected` |
| `lfu-pricing-quotes` | none | only a write-promotion policy toggle | n/a | reject / `rejected` |
| `lfu-product-catalog` | none | duplicates the bucket-index mechanism | n/a | reject / `rejected` |
| `lfu-route-planner` | none | duplicates lease-based victim exclusion | n/a | reject / `rejected` |
| `lfu-weather-forecast` | none | only a frequency constant/overflow toggle | n/a | reject / `rejected` |

## Findings

### LFU-F1 — renamed shared implementation template

**Severity:** major. **Status:** resolved and reverified.

The v2 superset header and generic victim scan were removed. The v3 owner uses
15 separate headers, owned representations, references, operation traces, and
false substitutes. Actual normalized family comparison is fail-closed.

### LFU-F2 — non-executed negative markers

**Severity:** major. **Status:** resolved and reverified.

Marker grep was deleted. Each counted root now includes a compilable false
substitute, and Docker CTest must reject at least one discovered test. The
canonical receipt records three of three rejected tests for every root.

### LFU-F3 — generic trace omitted profile operations

**Severity:** major. **Status:** resolved and reverified.

Each v3 oracle is task-specific, invokes every public operation class, and
checks return values plus the complete diagnostic state after every operation.
The operation bodies and boundary profiles are unique family-screen dimensions.

### LFU-F4 — receipt did not bind current owner and mount

**Severity:** moderate. **Status:** resolved and reverified.

The v3 receipt binds owner and reference hashes and independently recomputes
each root hash inside the archived Docker mount. The owner rejected an initial
receipt attempt when that independent hash procedure did not match, then reran
the full evidence after correcting the separator encoding.

## Conclusion

All 20 legacy roots are accounted for. Fifteen materially independent v3 roots
reached `local_family_verified`; five semantic/policy duplicates were rejected
and are not counted. Prompt boundaries, reference mapping, exact regeneration,
seven-dimension diversity, actual normalized family and holdout screening,
normal and fresh sanitizer execution, and compiled negative rejection pass.
Optional dataset handoff remains `not_requested`.
