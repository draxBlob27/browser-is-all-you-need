# Generate a Deterministic Aider Task-Family Specification

Inputs (the only inputs you will receive):

```text
TASK_FAMILY_ROOT=<absolute-or-repo-relative task-family directory>
SPEC_DOCUMENT_PATH=<absolute-or-repo-relative Markdown output path>
```

Create or replace only `SPEC_DOCUMENT_PATH`. Do not modify generated tasks,
generators, tests, datasets, or release artifacts.

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
3. Identify all objective, prompt, implementation, test, metadata, build,
   verifier, duplication, and contamination problems.
4. Assign every root exactly one disposition: `reject`, `replace`, or
   `repair-in-place`, using `verify-and-remedy.md`.
5. Specify for every retained/replacement root: complete C++17 API, data types,
   ownership, valid/invalid/duplicate/absent/empty behavior, mutation effect,
   ordering, ties, overflow, and public examples.
6. Specify exact internal representation, forbidden substitutes, invariant
   predicate, deterministic property-test seed/operation mapping, behavior
   oracle, and negative fixtures.
7. Specify editable-file order; all docs/test/reference/support/CMake/config/
   provenance roles; normal/sanitizer verifier; and family/benchmark screens.
8. Give each root an acceptance condition proving the previous trivial/bad
   implementation fails and the independent reference passes.
9. End with an ordered implementation plan and explicit non-claims.

Use normative language and exact values/algorithms. “Add tests,” “make
distinct,” “improve metadata,” or “use a real structure” is invalid unless it
also says precisely what to implement and how to prove it. Never claim
oracle verification, SFT suitability, release admission, or benchmark safety
without evidence. Keep private assets out of the specification.
