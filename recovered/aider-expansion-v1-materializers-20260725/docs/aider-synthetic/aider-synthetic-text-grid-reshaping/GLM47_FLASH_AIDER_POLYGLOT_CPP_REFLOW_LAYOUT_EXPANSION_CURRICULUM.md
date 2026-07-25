# Reflow And Layout Expansion Curriculum

Status: deterministic new-root specification for the 2,500-task expansion.
The terminal local status may be no stronger than `local_family_verified`.
This document does not authorize JSONL, a split, a dataset release, training,
or a benchmark-uplift claim.

## Identity and count contract

The family ID is `aider-expansion-v1-reflow-layout-v1`. It contributes exactly
30 new roots to the binding count-plan cell **Text normalization, reflow,
justification, and whitespace-sensitive layout / 30**. The only generated
family root is:

```text
.w8-biayn/data/aider-tasks-expansion-v1/
  text-grid-layout/
    reflow-layout/
```

Every task has lineage `new-root`. Neither `.w8-biayn/data/aider-tasks/` nor
`.w8-biayn/data/aider-tasks-reverify/` is an output. Before materialization the
owner must freeze all three inventories, reject ID collisions, compare emitted
semantic contracts with both existing trees, and refuse symlink or hardlink
escape. The existing 20-root `text-justification` family is reserved input: no
task below repeats its hanging-indent agenda, flight-telex segmentation,
protocol label columns, entry-block pagination, field tab stops, dialogue
boxes, column balancing, nested quotes, invoice tab stops, cubic line-break
penalty, widow repair, dosage hyphenation, centering, duration cues,
overlapping platform pages, quantity prefixes, poster scaling, newsletter
partition, typed address packing, or severity-run coalescing contract.

## Shared artifact contract

Each root is an offline C++17 Aider whole-file task. Its editable files are the
task-ID header followed by the task-ID source. The prompt exposes only
`.docs/introduction.md`, `.docs/instructions.md`, and those two coherent but
incomplete starter files. References, visible/private tests, negative
fixtures, CMake, provenance, manifests, and receipts remain private. Inputs
are ASCII bytes unless a contract explicitly names display cells; no task may
delegate to locale, regular-expression, formatting, terminal, Markdown, or
Unicode layout libraries.

Every public contract defines valid, invalid, duplicate, absent, empty,
boundary, ordering, tie, and overflow behavior. Invalid input returns a
root-specific result with `valid == false` and no partial payload. Valid empty
input behavior is stated per root. Arithmetic is bounded before addition or
multiplication. References use direct task-specific state and control flow.
Every root owns one compiling plausible-but-wrong source which the exact
visible/private production tests execute and reject.

## Thirty executable roots

| Task ID | Public capability and substantive mechanism | Boundary/tie rule | Coherent false substitute |
| --- | --- | --- | --- |
| `reflow-stream-fragments` | `StreamReflower::push/finish`; preserve tokenizer and paragraph-separator state across arbitrary chunk boundaries. | CR is invalid; two LF bytes terminate a paragraph; `finish` flushes one partial paragraph once. | Tokenize each chunk independently. |
| `layout-nested-bullets` | Render an explicit parent-index forest with connector prefixes and measured hanging text. | Parents precede children; sibling order is input order; depth and width are bounded. | Render a flat bullet list. |
| `reflow-markdown-blocks` | Classify fenced blocks and prose with a line-state machine; wrap prose while copying complete fences byte-for-byte. | Unclosed or indented fences are invalid; blank prose lines delimit paragraphs. | Normalize every line, including fenced bytes. |
| `layout-footnote-pages` | Backtracking page allocator reserves bottom rows for the references cited by each page. | A note first appears on the earliest page citing it; page ties keep the longest body prefix. | Paginate body first and append all notes at the end. |
| `reflow-comment-prefixes` | Group adjacent source-comment lines by exact prefix and rewrap payload with prefix-local continuation width. | Blank comments stay blank; prefix changes close a group; malformed lines are invalid. | Strip all prefixes and wrap one paragraph. |
| `layout-terminal-columns` | Parse ANSI SGR escapes as zero-cell spans and pad records using measured visible-cell widths. | Only complete CSI `m` sequences are accepted; ties preserve row order. | Count escape bytes as display cells. |
| `layout-path-ellipsis` | Fit normalized path components by preserving root and basename, then select the maximum contiguous suffix that fits with one ellipsis component. | `.` and `..` components are invalid; longest suffix wins, then earlier start. | Truncate raw bytes from the end. |
| `reflow-sentence-spacing` | Scan protected byte spans and sentence terminals; canonicalize whitespace only outside spans with policy-specific inter-sentence gaps. | Spans are sorted, disjoint, and in range; terminal runs count once. | Collapse all whitespace globally. |
| `layout-outline-tree` | Iterative depth-first outline renderer maintains last-sibling flags to choose vertical and elbow connectors. | Parent indices form one rooted acyclic tree; children keep input order. | Indent by depth without connector state. |
| `reflow-log-continuations` | Parse timestamp-led records, attach continuation fragments, and wrap under the measured timestamp gutter. | An orphan continuation is invalid; record order is stable; blank continuation is retained. | Treat every input line as a new record. |
| `layout-decimal-columns` | Validate signed decimal lexemes and align integer, decimal-point, and fractional fields without numeric conversion. | At most one point, at least one digit, no exponent; column maxima define padding. | Right-align whole strings. |
| `reflow-diff-hunks` | Preserve diff markers and wrap only payload bytes with marker-specific continuation prefixes. | Header lines are copied atomically; missing hunk header before changes is invalid. | Remove markers and wrap plain text. |
| `reflow-poetry-stanzas` | Split overlong verse only at declared caesura bytes and preserve exact stanza boundaries. | Choose the latest fitting caesura; no legal cut makes the input invalid. | Greedy word wrapping. |
| `layout-template-slots` | Measure atomic placeholder expansions before laying out literal/slot segments; emit source-to-output slot offsets. | Every placeholder has exactly one value; unknown/duplicate values are invalid. | Wrap the unexpanded template and substitute afterward. |
| `layout-gutter-line-numbers` | Compute the final decimal gutter width, wrap source lines, and render continuation gutters without numbers. | Numbering starts positive; overflow is checked; source blank lines consume numbers. | Recompute a different gutter width per line. |
| `layout-ruler-tabs` | Expand tabs against a strictly increasing repeating tab-stop cycle while retaining a source-to-output column map. | Empty stops, duplicates, or zero cycle width are invalid; exact-stop tabs advance. | Replace each tab with a constant number of spaces. |
| `layout-leader-lines` | Allocate dot leaders between validated labels and page numbers using shared page-number width. | At least two dots; labels remain left aligned; page numbers right align. | Pad each row from its own number width. |
| `reflow-rfc-headers` | Parse one field name plus semicolon-delimited atomic clauses and fold with a leading-space continuation. | No bare CR/LF, empty clause, or invalid field byte; clauses never split. | Wrap at arbitrary spaces. |
| `layout-glyph-kerning` | Compose rectangular ASCII glyph bitmaps, removing the maximum pairwise blank-column overlap while preserving ink. | Ragged glyphs are invalid; overlap ties take the maximum safe overlap. | Concatenate every glyph with a fixed one-column gap. |
| `reflow-punctuation-glue` | Tokenize words and punctuation classes, enforce no leading closing punctuation or trailing opening punctuation, then wrap glued groups. | Unbalanced opening/closing punctuation is invalid; stable token order. | Split on whitespace and insert spaces uniformly. |
| `layout-snake-columns` | Place fixed lines column-major with alternating top-down/bottom-up columns, then render row-major with shared widths and gutters. | Column count is positive and no larger than lines; incomplete final column is deterministic. | Fill every column top-down. |
| `layout-caption-skyline` | Pack rectangular caption boxes left-to-right using a skyline height vector and lowest-y/leftmost placement. | Invalid dimensions or impossible placement return invalid atomically. | Use a single row cursor and ignore vertical holes. |
| `reflow-alternating-justification` | Greedy line construction plus exact full-justification whose remainder direction alternates by emitted nonfinal line. | Single-word/final lines are left aligned; first remainder is left-to-right. | Always assign remainder from the left. |
| `layout-print-regions` | Partition ordered lines into fixed-height regions, repeat a header per region, and render regions side-by-side with a gutter. | Header consumes one row; short final regions pad with blanks. | Concatenate regions vertically. |
| `reflow-escaped-whitespace` | One-pass escape scanner treats escaped whitespace as literal bytes and canonicalizes only unescaped whitespace runs. | Dangling escape is invalid; escaped LF is data, not a paragraph boundary. | Decode escapes, then normalize everything. |
| `reflow-query-folding` | Parse `key=value` atoms separated by `&` and fold only between atoms with a continuation prefix. | Empty key/value, duplicate key, or invalid percent triplet is invalid. | Wrap the raw query at arbitrary bytes. |
| `layout-annotation-lanes` | Greedy interval coloring assigns nonoverlapping annotation spans to the lowest available lane and renders anchors above source text. | Spans are in range and nonempty; equal starts preserve input order. | Put every annotation in one lane. |
| `reflow-newline-canonicalization` | Streaming CRLF/LF scanner canonicalizes line endings and caps paragraph separators while preserving terminal-newline state. | Bare CR is invalid; more than two empty lines collapse to two; valid empty stays empty. | Replace CR bytes independently and trim the result. |
| `layout-marginal-notes` | Flow note words through a fixed side column starting at anchored main-line rows while main text remains immutable. | Anchors are sorted/in range; later notes start after occupied note rows. | Append notes after all main lines. |
| `layout-ruby-annotations` | Align atomic ASCII annotations above nonoverlapping base-text spans by expanding inter-span gaps without changing base-byte order. | Spans are sorted and nonempty; ties add padding to the right side of the annotated span. | Center annotations independently and let them overlap. |

## Diversity, clone, and contamination acceptance

The owner must reread emitted docs, public API, reference, visible/private
tests, and negative fixture for all `30 * 29 / 2 = 435` unordered pairs. Each
pair must differ materially and separately in exactly these seven dimensions:
`public_api`, `owned_state_algorithm`, `mutation_selection_rules`,
`invalid_boundary_behavior`, `reference_control_flow`,
`deterministic_oracle`, and `topic_negative_fixture`. A conjunction is
required; an aggregate score cannot pass a pair.

From one emitted root the owner must materialize complete coherent controls
for domain/identifier rename, constants/policy-only change, and opposite-end
selection. Each control must change the intended files, compile with strict
C++17, pass its internally consistent visible/private tests in normal and
fresh ASan/UBSan modes, and be rejected by the exact production pair
evaluator. Focused tests must independently inspect all 435 decisions, the
exact dimension set, control file changes, build coherence, and rejection.

The screen must also compare all 30 roots with every real root in both existing
trees and all 26 official Aider Polyglot C++ holdouts using normalized docs,
API, source, tests, and oracle logic. A slug, prompt, answer/reference hash,
semantic-lineage, or content conflict rejects the new root; renaming is not a
remedy. Rejected roots do not count and require a genuinely new backfill.

## Build, evidence, and completion

The repository-pinned C++ sanity image is used with `--network none`; the
evidence class is `docker_sanity`, not `locked_oracle`. The owner also exposes
`--verify-host`, which reruns the identical per-subject matrix (starters,
references, negatives, and coherent controls, clean normal plus fresh
ASan/UBSan builds, exactly two discovered tests per subject, negatives
executed and rejected) on the host toolchain and records a
`reflow-layout-host-verify-v1` receipt bound to the current tree, owner, and
host compiler/CMake identities. Host evidence supports host-only campaigns; it
never replaces the mandatory network-disabled Docker sanity gate required for
`local_family_verified`. Every retained root and
every coherent control must have positive equal normal and fresh ASan/UBSan
CTest discovery. Every per-root false substitute must compile under the same
strict flags and then fail at least one production test. The receipt binds the
owner, curriculum, focused test, exact task tree, deterministic archive and
mounted archive, prompts, starters, references, tests, policies, image,
compiler path/version/hash, CMake version, commands, and outcomes.

Creator preflight is followed by an immutable read-only audit. Any finding is
preserved, assigned a stable ID, routed through owner-controlled remediation,
complete regeneration, and a fresh audit. Exactly 30 fresh-audit-passing roots
are required for `local_family_verified`; a host-only pass, stale receipt,
review disposition, or missing Docker/holdout prerequisite yields
`not_completed`.
