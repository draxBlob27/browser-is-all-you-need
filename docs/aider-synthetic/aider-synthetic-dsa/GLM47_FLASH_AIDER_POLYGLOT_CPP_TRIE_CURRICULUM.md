# Trie Curriculum: Topic 1, Subtask 4

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This is the fourth subtask under **Linked Structure Invariants**. Its purpose
is to teach child-map consistency, prefix accounting, terminal marking, and
safe deletion through C++17 tasks with domain-specific public APIs.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

## Online Material Status

Trie exercises are available online in sources such as Open Data Structures,
Library Checker, and common programming judges. They are useful for private
concept study or source discovery only. They are not a drop-in SFT source
inventory: every external source needs explicit license and semantic
contamination review.

The tasks below materialize as newly authored C++17 roots. Their interfaces,
tests, reference implementations, and provenance must be created in-repo and
pass the normal original-task admission process.

## Proposed Original Tasks

| ID | Task | Visible contract |
|---|---|---|
| `trie-command-completion` | Command completion | Register or remove commands and return lexicographically ordered prefix matches. |
| `trie-product-search` | Product search | Add product codes, count prefix matches, and return a bounded suggestion list. |
| `trie-contact-directory` | Contact directory | Add, rename, delete, and search contacts by case-normalized prefix. |
| `trie-library-call-prefixes` | Library call prefixes | Maintain call-number strings and count entries beneath a prefix. |
| `trie-word-game-dictionary` | Word-game dictionary | Insert words, test membership, and find valid words from a required prefix. |
| `trie-url-router` | URL router | Register path segments and resolve the longest matching route. |
| `trie-dns-suffixes` | DNS suffixes | Register domain suffix rules and resolve the most-specific matching suffix. |
| `trie-dna-motifs` | DNA motifs | Store DNA motifs, reject invalid symbols, and count matching prefixes. |
| `trie-emoji-shortcodes` | Emoji shortcodes | Add and remove shortcode aliases and expand unique prefixes only. |
| `trie-spell-checker` | Spell checker | Load words, test exact spelling, and produce nearby prefix suggestions. |
| `trie-file-path-index` | File-path index | Register slash-separated paths and count descendants under a directory. |
| `trie-license-plate-index` | License-plate index | Normalize plate strings, reserve or release them, and query a prefix count. |
| `trie-predictive-text` | Predictive text | Maintain word frequencies and return top completions with deterministic ties. |
| `trie-snippet-tags` | Snippet tags | Index tagged snippets and return IDs matching a tag prefix. |
| `trie-log-category-filter` | Log category filter | Register dotted category names and select all categories under a prefix. |
| `trie-morse-codebook` | Morse codebook | Insert symbol encodings and reject codes that violate a prefix-free policy. |
| `trie-access-token-prefixes` | Access-token prefixes | Store opaque token strings, revoke them, and reject ambiguous short prefixes. |
| `trie-sku-allocator` | SKU allocator | Allocate patterned SKU strings and find the first available suffix under a prefix. |
| `trie-wildcard-dictionary` | Wildcard dictionary | Match words with a single-character wildcard while preserving terminal semantics. |
| `trie-translation-glossary` | Translation glossary | Maintain language-qualified terms and resolve exact and prefix lookups. |

## Materialization Requirements

Every root needs a task-specific C++17 public API; do not expose generic
`insert(word)` and `search(word)` methods as the visible assignment. The
normalization policy, duplicate policy, query behavior, ordering, and
invalid-input behavior must materially differ between roots.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

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

## Admission Boundary

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
