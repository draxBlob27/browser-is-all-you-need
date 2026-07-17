# Nested Structure Validation Curriculum: Decontaminated Matching-Brackets Capability

Status: curriculum-design note. This document proposes original task concepts;
it does not claim that they are admitted SFT roots or available as an online
dataset.

This curriculum targets stack-based structured validation: nested scopes,
typed delimiters, escaping, quoted regions, comments, diagnostics, and
incremental input. It does **not** propose renamed copies of a bare balanced-
brackets predicate.

Use this with:

- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_STRUGGLE_CONTEXT.md`
- `docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_ALGORITHM_DATA_STRUCTURE_TOPICS.md`
- `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`

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

## Proposed Decontaminated Tasks

| ID | Task | Visible contract |
|---|---|---|
| `nest-config-sections` | Config-section validator | Validate named `begin`/`end` sections with nesting and report the first unmatched section name. |
| `nest-template-placeholders` | Template placeholder parser | Parse nested `{{...}}` placeholders while allowing escaped braces in literal text. |
| `nest-rich-text-tags` | Rich-text tag validator | Validate typed opening/closing tags with quoted attributes and return line/column diagnostics. |
| `nest-code-fences` | Code-fence checker | Verify fenced code blocks with language labels while ignoring fence-like text inside quoted strings. |
| `nest-workflow-scopes` | Workflow scope checker | Validate `open`/`close` workflow scopes and return the remaining unclosed scope stack. |
| `nest-query-groups` | Query-group parser | Parse nested boolean groups with comments and identify the first invalid operator placement. |
| `nest-math-expressions` | Math-expression scanner | Validate grouping tokens while accepting unary operators and scientific-notation signs. |
| `nest-markdown-links` | Markdown link parser | Extract balanced link labels/destinations with escaped parentheses and report malformed spans. |
| `nest-script-comments` | Script-comment stripper | Remove nested block comments while preserving string and character literal contents. |
| `nest-command-blocks` | Command-block validator | Validate command blocks with explicit terminators and optional labels. |
| `nest-json-stream` | JSON-like stream checker | Incrementally validate object/array nesting across chunks and return incomplete-state diagnostics. |
| `nest-regex-groups` | Regex-group inspector | Count typed capture groups while ignoring escaped parentheses and character classes. |
| `nest-protocol-frames` | Protocol-frame parser | Decode nested binary frame markers and reject invalid length-delimited closures. |
| `nest-spreadsheet-formulas` | Spreadsheet formula checker | Validate function argument nesting and separator placement under locale-specific delimiters. |
| `nest-recipe-steps` | Recipe-step structure | Validate nested preparation blocks with indentation-derived closures and explicit end markers. |
| `nest-legal-clauses` | Legal-clause numbering | Check hierarchical clause numbering and return the first invalid parent/child transition. |
| `nest-diagram-groups` | Diagram group parser | Validate nested drawing groups and ensure every referenced group is currently open. |
| `nest-chat-quotes` | Chat-quote formatter | Match quote markers across lines while exempting fenced snippets and escaped markers. |
| `nest-access-policies` | Access-policy validator | Validate nested allow/deny scopes and detect an invalid scope override. |
| `nest-build-directives` | Build-directive parser | Parse nested build directives, includes, and conditionals with precise unmatched-directive errors. |

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

This document is not authorization to bypass the primary Aider SFT pipeline.
Before any task is added to a dataset, it must pass source licensing,
provenance, compiler-image, oracle, sanitizer, contamination, split-family,
rendering, token/mask, and release verification gates.
