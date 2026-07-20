# Generate a Deterministic Aider Task-Family Specification

Inputs (the only inputs you will receive):

```text
TASK_FAMILY_ROOT=<absolute-or-repo-relative task-family directory>
SPEC_DOCUMENT_PATH=<absolute-or-repo-relative Markdown output path>
```

Create or replace only `SPEC_DOCUMENT_PATH`. Do not modify generated tasks,
generators, tests, datasets, or release artifacts.

This prompt applies to every topic and every directory depth beneath
`.w8-biayn/data/aider-tasks/` and parallel
`.w8-biayn/data/aider-tasks-reverify/` materializations. The Priority-1 goal is
to specify a genuine implementation of the concept advertised by each task.
The substantive representation, algorithm, state transition, or systems
mechanism must not be delegated to a library/container, third-party facility,
precomputed answer, hard-coded cases, renamed wrapper, or other topic-specific
false substitute. Incidental output vectors, temporary buffers/worklists,
strings, ownership helpers, and metadata lookups are allowed when they do not
replace the claimed core mechanism.

Read: `AGENTS.md`, `README.md`, `ROADMAP.md`,
`.agents/skills/w8-biayn-framework/SKILL.md`,
`docs/AIDER_SFT_SCOPE.md`,
`docs/aider-tasks-spec/Original-specs.md`,
`docs/aider-tasks-spec/verify-and-remedy.md`, and every generator, materializer,
focused test, generated root, prompt-facing document, metadata record, starter,
reference, visible/private test, and CMake file reachable from
`TASK_FAMILY_ROOT`. Also locate the official benchmark-holdout manifest and the
relevant prompt code. Discover every other path from the two inputs.

Write an implementation-grade specification, not a high-level audit. It must:

1. Inventory every root, generator, and current evidence/status.
2. Compare every root with the original Aider whole-file task contract.
3. For every root, name its advertised core representation, algorithm, state
   transition, or systems mechanism; locate the current substantive
   implementation; identify its easiest topic-specific false substitute; and
   record `primary_core_objective: achieved|not_achieved` with source/test
   evidence. Successful compilation, examples, documentation, or metadata do
   not establish this result.
4. Identify all secondary prompt, test, metadata, build, verifier, duplication,
   contamination, provenance, and reproducibility problems separately from the
   primary core-objective result.
5. Assign every root exactly one disposition: `reject`, `replace`, or
   `repair-in-place`, using `verify-and-remedy.md`.
6. Specify for every retained/replacement root: complete C++17 API, data types,
   ownership, valid/invalid/duplicate/absent/empty behavior, mutation effect,
   ordering, ties, overflow, and public examples.
7. Specify the exact core implementation first: owned state, substantive
   operations, permitted incidental library use, topic-specific forbidden
   substitutes, invariant/property predicate, deterministic property-test
   seed/operation mapping, behavior oracle, and negative fixtures.
8. Specify editable-file order; all docs/test/reference/support/CMake/config/
   provenance roles; normal/sanitizer verifier; and family/benchmark screens.
9. Give each root a primary acceptance condition proving the genuine advertised
   mechanism is present and the prior/topic-specific false substitute fails.
   Then list the secondary acceptance conditions under separate headings.
10. End with an ordered implementation plan that implements and verifies the
    primary core objective before secondary remediation, plus explicit
    non-claims.

Use normative language and exact values/algorithms. “Add tests,” “make
distinct,” “improve metadata,” or “use a real structure” is invalid unless it
also says precisely what to implement and how to prove it. Never claim
oracle verification, SFT suitability, release admission, or benchmark safety
without evidence. Keep private assets out of the specification.
