# Nested Structure Validation Curriculum: Decontaminated Matching-Brackets Capability

Status: v2 local-family remediation specification. The legacy materialization
is preserved as audit input; 20 replacement roots are generator-owned beneath
the parallel re-verification tree. This is not a dataset or training claim.

This curriculum targets stack-based structured validation: nested scopes,
typed delimiters, escaping, quoted regions, comments, diagnostics, and
incremental input. It does **not** propose renamed copies of a bare balanced-
brackets predicate.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/AIDER_SFT_SCOPE.md`

## Decontamination Boundary

The official Aider C++ benchmark holdout set remains excluded in its entirety.
Do not use any holdout wording, APIs, classes, field names, examples, tests,
references, or model outputs. Do not construct a candidate by paraphrasing an
online bracket-matching exercise.

The existing repository source inventory also contains a `matching-brackets`
root. Do not derive these candidates from that root, its scaffold, its tests,
or its reference. Treat it as an excluded source family for this curriculum.

Each candidate below must be independently authored and materially differ from
all excluded roots in at least three dimensions: token grammar, nesting rule,
quoted/comment behavior, streaming model, returned diagnostic, recovery/error
policy, input representation, and visible C++ API. Run the repository's
whole-slug benchmark denylist and semantic contamination checks before
admission. Reject and backfill every near-match; do not weaken the checker.

## Online Material Status

Nested-delimiter examples are available online, but they are useful only for
private concept study or source discovery. They are not a drop-in SFT source
inventory: every external source needs explicit license and semantic
contamination review.

The following tasks materialize as newly authored C++17 roots. Their
interfaces, tests, reference implementations, and provenance must be created
in-repo and pass the normal original-task admission process.

## V2 Replacement Inventory

Each row has a different public API, state model, core algorithm, and negative
fixture. A shared scanner with renamed delimiter tokens is expressly forbidden.

| ID | Primary mechanism | Observable contract |
|---|---|---|
| `nest-access-policies-v2` | Typed policy-event interpreter | Apply inherited allow/deny decisions and reject allow escalation below deny. |
| `nest-build-directives-v2` | Conditional frame evaluator | Resolve nested `#if/#else/#endif` branches against a symbol set. |
| `nest-chat-quotes-v2` | Line-depth/fence state machine | Audit quote-depth transitions while excluding fenced snippet lines. |
| `nest-code-fences-v2` | Marker-length/language extractor | Extract compatible backtick/tilde blocks; short closers remain code. |
| `nest-command-blocks-v2` | Labeled transaction interpreter | Enforce active-label uniqueness and current-label run/end semantics. |
| `nest-config-sections-v2` | Path/key record parser | Build section paths and enforce key uniqueness per path, not globally. |
| `nest-diagram-groups-v2` | Current-ancestor resolver | Resolve references only to an open ancestor, never a historical group. |
| `nest-json-stream-v2` | Incremental lexical validator | Preserve container/string/escape/error state across arbitrary chunks. |
| `nest-legal-clauses-v2` | Numeric hierarchy automaton | Require existing parents and consecutive sibling component numbers. |
| `nest-markdown-links-v2` | Multi-phase span scanner | Extract labels and nested destinations with escapes and half-open spans. |
| `nest-math-expressions-v2` | Lexer, shunting yard, evaluator | Produce postfix and a checked value with unary/scientific support. |
| `nest-protocol-frames-v2` | Binary TLV boundary decoder | Decode opaque or child-frame payloads against exact declared lengths. |
| `nest-query-groups-v2` | Boolean precedence parser | Produce postfix with unary NOT and AND/OR precedence plus comments. |
| `nest-recipe-steps-v2` | Indentation lifecycle parser | Build step paths with sibling-local uniqueness and explicit completion. |
| `nest-regex-groups-v2` | Regex lexical classifier | Count capture kinds while honoring escapes, classes, names, and prefixes. |
| `nest-rich-text-tags-v2` | Tag/attribute lexer | Validate names, quoted attributes, void tags, and line/column errors. |
| `nest-script-comments-v2` | Position-preserving comment machine | Strip nested comments while retaining literal bytes and newlines. |
| `nest-spreadsheet-formulas-v2` | Locale-aware call-frame parser | Report nested function arities without globally splitting separators. |
| `nest-template-placeholders-v2` | Parent-linked placeholder parser | Return preorder placeholder records with parents, defaults, and spans. |
| `nest-workflow-scopes-v2` | Parent/lifecycle event model | Enforce declared parents and direct task completion before scope close. |

The planning count remains an inventory, not a quota. Any root that collapses
to another row's normalized state transition must be replaced rather than
retained under a new noun.

## Materialization Requirements

Every root needs a task-specific C++17 public API. Do not expose a function
that simply returns whether a character string has balanced brackets. Include
the typed grammar, tokenization/escaping behavior, streaming state where
applicable, result/diagnostic type, and invalid-input policy in the starter
interface.

For each task, author a documented provenance record, starter header/source
pair, independent reference implementation, visible examples, hidden Catch
tests, normal build, and fresh locked sanitizer build.

Hidden tests must cover:

- empty input, only literal text, and deeply nested valid structures;
- unexpected closer, mismatched closer, and end-of-input with unclosed state;
- escaped delimiters, quoted strings, character literals, and comment regions
  where applicable;
- ambiguous marker sequences and deterministic first-error position;
- valid nested structures split across stream chunks where the API is
  incremental;
- malformed token lengths, invalid names, and no-state-mutation behavior for
  mutable/incremental parsers;
- large nesting depth handled without recursion overflow where required;
- randomized grammar-derived cases checked against an independent parser oracle;
- a final contamination screen proving the candidate remains outside benchmark
  and excluded-source families.

## Admission Boundary

This document does not authorize SFT rows, training, or benchmark claims under the current local task-authoring scope.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.

## Reverification Contract

- Selected prompt: `docs/aider-tasks-spec/prompts/remediate-family-reverify.md`.
- Legacy root: `.w8-biayn/data/aider-tasks/aider-dsa/nested-structure/` (immutable audit input).
- V2 root: `.w8-biayn/data/aider-tasks-reverify/aider-dsa/nested-structure/`.
- Owner: `src/w8_biayn/integrations/moonlight_nested_structure_aider_tasks.py`
  plus its hand-authored case module and focused test.
- All 20 legacy roots have disposition `replace` because their references and
  tests implement the same token-parameterized delimiter scan.
- `--verify-core` must prove fresh generator equality, prompt/role boundaries,
  distinct normalized family mechanisms, and semantic screening against the
  bound 26-root C++ holdout inventory.
- `--verify` additionally requires the designated locked image, network-off
  normal and fresh ASan/UBSan builds, equal positive discovery counts, mounted
  tree-hash equality, and an executed failing negative fixture per root.

The strongest allowed terminal state is `local_family_verified`; optional
dataset handoff is `not_requested`.
