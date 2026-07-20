# Trie Curriculum: Topic 1, Subtask 4

Status: task-spec-v3 local family verified. The original 20 generated roots are
immutable audit inputs; 20 one-to-one replacements are generator owned under
the parallel re-verification root. The first v2 verification claim was
invalidated, then reverified with artifact-derived five-dimension all-pairs
evidence and mandatory identifier-renamed, constants/policy-only, and
opposite-end adversarial controls. This does not claim admitted SFT roots or an
online dataset.

This is the fourth subtask under **Linked Structure Invariants**. Its purpose
is to teach child-map consistency, prefix accounting, terminal marking, and
safe deletion through C++17 tasks with domain-specific public APIs.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

## Online Material Status

Trie exercises are available online in sources such as Open Data Structures,
Library Checker, and common programming judges. They are useful for private
concept study or source discovery only. They are not a drop-in SFT source
inventory: every external source needs explicit license and semantic
contamination review.

The tasks below materialize as newly authored C++17 roots. Their interfaces,
tests, reference implementations, and provenance must be created in-repo and
pass the normal original-task admission process.

## Legacy Audit And V2 Replacement Inventory

The legacy roots all delegated authority to the same flat
`std::map<std::string, int>` scan/sort template. They are preserved at
`.w8-biayn/data/aider-tasks/aider-dsa/trie/` and have disposition `replace`.
The v2 roots materialize only at
`.w8-biayn/data/aider-tasks-reverify/aider-dsa/trie/`.

| Legacy ID | V2 replacement | Distinguishing mechanism |
|---|---|---|
| `trie-command-completion` | `radix-command-catalog` | compressed radix edges and merge-on-erase |
| `trie-product-search` | `tst-product-prefix` | ternary-search-trie traversal |
| `trie-contact-directory` | `contact-alias-trie` | normalized alias paths with contact ownership |
| `trie-library-call-prefixes` | `digit-call-range-trie` | digit paths with subtree counts |
| `trie-word-game-dictionary` | `rack-prefix-word-trie` | rack-budget DFS from a required prefix |
| `trie-url-router` | `segment-route-dispatch-trie` | segment edges and longest ancestor route |
| `trie-dns-suffixes` | `reversed-domain-policy-trie` | reversed labels and most-specific suffix policy |
| `trie-dna-motifs` | `dna-motif-counter-trie` | fixed DNA branches and prefix counts |
| `trie-emoji-shortcodes` | `unique-shortcode-trie` | terminal-count uniqueness resolution |
| `trie-spell-checker` | `levenshtein-spell-trie` | row-propagating edit-distance traversal |
| `trie-file-path-index` | `path-descendant-trie` | segment hierarchy with file/byte aggregates |
| `trie-license-plate-index` | `normalized-plate-reservation-trie` | normalized alphanumeric paths and prefix uniqueness |
| `trie-predictive-text` | `cached-topk-text-trie` | per-node ranked completion caches |
| `trie-snippet-tags` | `tag-posting-trie` | terminal posting sets and prefix union |
| `trie-log-category-filter` | `hierarchical-log-policy-trie` | inherited dotted-category policy |
| `trie-morse-codebook` | `prefix-free-morse-trie` | prefix-free code admission |
| `trie-access-token-prefixes` | `shortest-token-prefix-trie` | terminal cardinality and shortest unique prefix |
| `trie-sku-allocator` | `numeric-sku-allocation-trie` | occupancy-guided smallest-gap allocation |
| `trie-wildcard-dictionary` | `single-wildcard-word-trie` | exact-depth wildcard branch traversal |
| `trie-translation-glossary` | `multilingual-glossary-trie` | language-partitioned owned tries |

## Materialization Requirements

Every root needs a task-specific C++17 public API; do not expose generic
`insert(word)` and `search(word)` methods as the visible assignment. The
normalization policy, duplicate policy, query behavior, ordering, and
invalid-input behavior must materially differ between roots.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible and private tests, normal
build, and fresh sanitizer build. The family has no separately designated
locked oracle image, so the pinned network-disabled C++ image is recorded as
`docker_sanity` with `locked_oracle: false`.

Hidden tests must cover:

- a prefix that is both a valid terminal key and an internal node;
- insertion and deletion of keys that share a long prefix;
- deletion that removes unreachable child maps but preserves shared prefixes;
- empty keys and invalid characters under the task-specific policy;
- duplicate insertion and repeated deletion behavior;
- deterministic result ordering and result limits where applicable;
- prefix counts after every mutation;
- long randomized mutation sequences checked against a normalized
  `std::map` or sorted-vector oracle.

The task-spec-v3 hard-rule test separately invokes every public operation
class and compares complete observable state with an independent value model
after every mutation. The owner compares emitted docs, public API/state,
reference control flow, public oracle, and private value oracle for all 190
unordered pairs. Its focused suite must reject identifier-renamed,
constants/policy-only, and opposite-end-selection clones. Each root owns a
distinct named false substitute; all substitutes compile under the reference's
strict flags and must be rejected by executed tests.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
