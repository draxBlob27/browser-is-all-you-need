# Sequence Pattern Curriculum: Decontaminated Sublist Capability

Status: remediated local-family curriculum. The legacy generic matcher family
is preserved as audit input; v2 replacements materialize only beneath the
parallel reverify root. This does not claim dataset admission or availability.

The official Aider Polyglot C++ `sublist` task is a permanent benchmark
holdout. This document does **not** propose renamed exercises that classify two
lists as equal, sublist, superlist, or unequal. It targets broader ordered
sequence reasoning through distinct matching, alignment, span, and policy
contracts.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

Do not use the holdout task's wording, API, data model, examples, tests,
reference implementation, or four-way relationship classification. Do not
construct a source candidate by paraphrasing or translating the holdout.

Each candidate below must be independently authored from a new behavior
specification and must materially differ in at least three of these dimensions:

- input structure, such as tokens, events, typed records, or normalized text;
- matching mode, such as wildcard, tolerance, case folding, gaps, or overlap;
- returned result, such as spans, counts, diagnostics, alignment, or a policy
  decision rather than list relationship classification;
- mutation, stream, multi-pattern, or query semantics;
- visible C++ API, error behavior, and ordering rules.

Before admission, run the repository's whole-slug benchmark denylist and
semantic contamination checks against all official Aider C++ roots. A
near-match, including any straightforward two-list relationship classifier, is
rejected. Preserve rejection evidence and backfill with a new independently
designed candidate; never weaken the checker.

## Online Material Status

Sequence-matching problems are available online, but they are useful only for
private concept study or source discovery. They are not a drop-in SFT source
inventory: every external source needs explicit license and semantic
contamination review.

The following tasks materialize as independently authored C++17 replacement
roots. Exact APIs, invariants, negative fixtures, remedy records, and acceptance
commands are specified in
`docs/aider-tasks-spec/aider-dsa/sequence-pattern.md` and the per-root remedy
specifications under the reverify tree's sibling `.state/remedy/` directory.

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `audit-event-kmp-v2` | Typed audit-event KMP | Prefix-function matching over typed event keys with overlapping spans. |
| `dna-shift-and-v2` | IUPAC Shift-And | Bit-parallel motif masks with invalid-character diagnostics. |
| `command-aho-policy-v2` | Command policy automaton | Aho-Corasick multi-policy matching with deterministic priority ties. |
| `playlist-gap-alignment-v2` | Playlist gap alignment | Minimum-gap DP alignment with unavailable tracks and folded IDs. |
| `sensor-stream-window-v2` | Sensor stream window | Stateful fixed-ring tolerance matching with monotonic sequence IDs. |
| `checkpoint-gap-dp-v2` | Checkpoint gap verifier | Timestamp-bounded subsequence DP and witness reconstruction. |
| `log-lexer-kmp-v2` | Coordinate log lexer | Punctuation-aware tokenization followed by KMP over mapped coordinates. |
| `ui-workflow-dfa-v2` | UI workflow DFA | Explicit ignore/reset/restart state transitions. |
| `factory-z-cycle-v2` | Factory Z-cycle | Z-box overlap counting and longest partial-cycle evidence. |
| `handshake-schema-machine-v2` | Handshake schema machine | Required, optional, and repeatable protocol-field states. |
| `route-rabin-karp-v2` | Route Rabin-Karp | Rolling hash over location-direction pairs with collision verification. |
| `dose-window-deque-v2` | Dose time-window policy | Expiring deque state for nonadjacent A-B-A class violations. |
| `price-movement-prefix-v2` | Relative price movements | Derived movement alphabet plus prefix-function matching. |
| `heading-lcs-alignment-v2` | Heading LCS alignment | Normalized LCS with deterministic witness reconstruction. |
| `access-gap-nfa-v2` | Access escalation NFA | Multiple bounded-gap rule states with implicated event IDs. |
| `combo-wildcard-trie-v2` | Combo wildcard trie | Multi-combo literal/wildcard trie and longest-match policy. |
| `support-suffix-automaton-v2` | Support macro automaton | Longest nonoverlapping repeated factor after quote filtering. |
| `inspection-optional-dp-v2` | Optional inspection DP | Match/skip DP with maximum-consumption witness. |
| `quote-product-window-v2` | Directed quote product | Continuous currency-cycle products with finite arithmetic checks. |
| `migration-dag-validator-v2` | Migration DAG validation | Topological graph validation followed by prerequisite-ordered application. |

## Materialization Requirements

The local remediation inventory is exactly 20 counted roots.  The owner and
focused tests must fail closed below or above that bound; count compliance does
not permit a renamed or policy-toggled duplicate.

Every root needs the task-specific C++17 API and primary mechanism named above.
Do not expose a generic two-vector relationship classifier. Input
normalization, result type, invalid-input behavior, ordering/ties, reference
control flow, and executed negative fixture must remain materially distinct.

The hard diversity screen must derive its evidence from each root's emitted
introduction and instructions, public header/API, reference source, visible
tests, and private tests, then compare all 190 unordered pairs.  Task IDs,
semantic-profile labels, and unequal raw hashes are not evidence.  Focused
adversarial controls must prove rejection of a domain/identifier-renamed clone,
a constants-or-policy-only clone, and an opposite-end-selection clone.

For each task, author a documented provenance record, coherent starter pair,
independent reference, visible/private tests, and a compilable false substitute.
The owner must discover exactly three CTest entries in clean normal and fresh
ASan/UBSan builds inside the network-disabled Docker sanity image.

Hidden tests must cover:

- empty streams and task-specific empty-pattern semantics;
- first, last, adjacent, and overlapping valid matches;
- no match, multiple matches, and deterministic span ordering;
- normalization, wildcard, tolerance, optional-step, or ignored-event rules
  where applicable;
- malformed typed events and no-state-mutation behavior for streaming tasks;
- boundary spans at the beginning and end of input;
- large adversarial inputs that distinguish intended linear/near-linear matching
  from pathological repeated rescans where the task specifies a complexity goal;
- adversarial cases checked against a straightforward task-specific oracle;
- a final contamination screen proving the candidate remains outside the
  benchmark holdout family.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
