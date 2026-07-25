---
name: aider-sft-task-spec
description: Write a per-task failure-learning document for Aider Polyglot C++ benchmark failures that ends in 20-50 concrete synthetic SFT task specifications. Use after diagnosing a failed Aider C++ task (see aider-output-diagnoser) when Codex must produce a durable docs/aider-learnings/<task>.md that specifies new training tasks with exact API shapes and the capability each one targets.
---

# Aider SFT Task Spec Writer

## Purpose

Turn one diagnosed Aider Polyglot C++ task failure into a durable learning document at
`docs/aider-learnings/<task>.md`. The document pairs evidence-based failure analysis
(from the `aider-output-diagnoser` skill) with a forward-looking dataset plan: 20-50
synthetic training-task specifications whose APIs and target capabilities directly
address what the model lacked.

Companion skill: `skills/aider-output-diagnoser/SKILL.md` (diagnosis workflow,
source-of-truth rules, answer-blind rule). This skill defines the output document.

## Ground-Truth Rules (non-negotiable)

- The benchmark checkout `polyglot-benchmark/` is read-only ground truth. Never edit it.
- Reference solution = `.meta/example.cpp` / `.meta/example.h` in the exercise dir.
- Tests = `<task>_test.cpp` in the exercise dir. Starter files at the root are NOT the solution.
- If `.meta/example.*` is missing or genuinely faulty, stop and report; never invent a contract.
- Stay answer-blind: derive abstract API/capability requirements from the reference, but never
  copy benchmark test fixtures or reference code into training task specs or target answers.

## Required Document Structure

File: `docs/aider-learnings/<task>.md`

1. **Task Identity & Evidence Pointers** — task slug, shard, outcome array (e.g. `[False, False]`),
   failure-log section line range, ground-truth file paths, existing analog dir if any
   (`aider-fixed26-analogs/fixed26-bNNN-<task>/`).
2. **Benchmark Contract (Ground Truth)** — exact file set, namespace, public API signatures
   (from `.meta/example.h`), exception policy, edge cases, and output-format constraints,
   each tied to the test file that enforces it. Quote with file:line.
3. **Failure Anatomy** — what the model emitted on attempt 1 and on each retry, where it
   diverged from the contract, and the proving evidence: quoted failure-log excerpts with
   the log's own source line numbers (e.g. `failure log line 458`) plus compiler/test output.
   Separate hard evidence (diffs, compiler errors) from inference (root-cause category).
4. **Knowledge / Capability Gaps** — the specific things the model lacked: C++ idiom knowledge,
   API-design judgment, header/impl separation discipline, edge-case reasoning, exception
   policy awareness, format-contract compliance, retry-repair behavior, context budgeting.
   Each gap must cite the failure anatomy item that proves it.
5. **SFT Task Specifications (20-50 specs)** — the core deliverable. See below.
6. **Acceptance & Validation Gates** — how rows built from these specs are validated before
   training: parser validity of the Aider file-listing format, compile+test receipts,
   hidden-edge coverage, contamination check against the benchmark, whole-file output rule.
7. **Cross-Check Statement** — a dated note listing what was re-verified (every cited log
   line re-read, every API claim re-checked against `.meta/example.*` and the test file)
   and any corrections made during cross-checking.

## SFT Task Specification Format (20-50 per document)

Each spec is one synthetic training task that teaches ONE capability the model lacked.
Specs must be concrete enough that a dataset author can implement them without further
design work. Use this exact per-spec shape:

```
### Spec NN: <kebab-case-slug>
- Files: <name>.cpp, <name>.h  (test file: <name>_test.cpp)
- API: namespace <ns>; exact function/class signatures with return types,
  parameter types, const/ref qualifiers; exception types and throw conditions.
- Prompt shape: one-line description of the story/domain wrapper (must NOT reuse
  the benchmark task's story) and which starter state the model sees.
- Target capability: the single skill this row teaches, mapped back to the gap in
  section 4 it repairs (e.g. "Gap G2 — exception policy: throw std::invalid_argument
  on radix < 2").
- Target answer shape: what a correct model response looks like (whole-file listings,
  header+impl split, includes used) — described, not copied from the reference.
- Difficulty / variation: what makes this spec distinct from its siblings.
```

Rules for the spec set as a whole:

- 20-50 specs, ordered from foundational (format discipline, signature fidelity) to
  advanced (edge cases, state semantics, overflow, repair turns).
- Cover EVERY gap from section 4 at least twice with different domains.
- Include at least: 2 format-contract specs (Aider whole-file listing discipline),
  2 header/impl-separation specs, 2 exception-policy specs (when the contract has one),
  3+ edge-case specs, 2 repair/retry specs (first answer is wrong, second turn fixes it),
  and 1 contrastive/negative spec (common wrong approach vs correct one).
- Domain variety: no two specs should share the same story wrapper.
- Granularity reference: `aider-fixed26-analogs/fixed26-b001-all-your-base/` shows 50
  implemented analogs for one task — match that level of API concreteness, but write
  specs only; do NOT implement the tasks.

## Cross-Check Protocol (mandatory)

Before finishing, the author must:
1. Re-read every failure-log line range cited in the doc and confirm the quote matches.
2. Re-check every API claim against `.meta/example.h`, `.meta/example.cpp`, and the test file.
3. Confirm the outcome array and shard match the run summary.
4. Record the result in section 7, including any claim that was corrected.
