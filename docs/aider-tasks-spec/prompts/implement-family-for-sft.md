# Implement a Local Aider Task Family Until It Is Verified

Inputs (the only inputs you will receive):

```text
TASK_FAMILY_ROOT=<absolute-or-repo-relative task-family directory>
SPEC_DOCUMENT_PATH=<absolute-or-repo-relative deterministic family specification>
```

Implement the family described by `SPEC_DOCUMENT_PATH`; use
`TASK_FAMILY_ROOT` as its generated/local artifact location. Discover all other
paths from the repository.

This prompt applies to every topic and every directory depth beneath
`.w8-biayn/data/aider-tasks/` and parallel
`.w8-biayn/data/aider-tasks-reverify/` materializations. Priority 1 is the
genuine implementation of each task's advertised representation, algorithm,
state transition, or systems mechanism. A buildable wrapper around a generic
container/library, third-party facility, precomputed answer, hard-coded cases,
or renamed shortcut does not achieve the task's central goal. Incidental output
vectors, temporary buffers/worklists, strings, ownership helpers, and metadata
lookups remain allowed when they do not replace the substantive mechanism.

Read: `AGENTS.md`, `README.md`, `ROADMAP.md`,
`.agents/skills/w8-biayn-framework/SKILL.md`,
`docs/AIDER_SFT_SCOPE.md`,
`docs/aider-tasks-spec/Original-specs.md`,
`docs/aider-tasks-spec/verify-and-remedy.md`, `SPEC_DOCUMENT_PATH`, its
generator/materializer/focused tests, the benchmark manifest, and the relevant
prompt-boundary implementation.

Rules:

1. Treat `SPEC_DOCUMENT_PATH` as normative. Report a policy contradiction;
   never silently weaken it.
2. Before secondary remediation, audit every root and record
   `primary_core_objective: achieved|not_achieved` with exact source/test
   evidence. Name the claimed mechanism and its easiest topic-specific false
   substitute. Compilation, public examples, documentation, metadata, or a
   receipt alone cannot establish `achieved`.
3. Implement and deterministically verify the advertised core mechanism first.
   Do not mark a root `implemented` or spend the handoff claiming completion
   from secondary polish while the primary core objective is absent.
4. Create the per-root remediation records/specifications and obey the
   disposition/state-machine rules in `verify-and-remedy.md`.
5. Never hand-edit generated task output. Change the owning generator,
   scaffold, config, renderer, and focused tests, then regenerate the family.
6. Implement every specified core representation/algorithm/state mechanism,
   API, starter, independent reference, invariant, topic-specific
   forbidden-substitute rule, public/private test, metadata/provenance field,
   CMake/Catch setting, and verifier receipt. Treat everything after the core
   implementation as a secondary completion requirement.
7. Add deterministic, topic-specific negative fixtures showing the prior
   trivial/template or delegated implementation fails. Do not reuse a
   balanced-tree banned-container list as the sole test for unrelated topics.
   Renaming or a happy-path test is not a remedy.
8. Keep private references/tests/provenance/CMake/receipts out of prompts.
9. Run the strongest available normal and fresh ASan/UBSan reference verification,
   recording missing runtime prerequisites rather than inferring a result.
10. Run semantic/slug benchmark-contamination and duplicate/family screening.
    Reject or replace required roots; never waive a near-match by renaming.
11. Do not create one-off JSONL or claim a dataset release from local artifacts.
12. Mark a family `local_family_verified` only after regeneration, prompt-boundary
    validation, normal/sanitizer evidence, and benchmark/family screening pass.
    Do not claim a dataset release.

For every root, update the audit/specification first with
`primary_core_objective: achieved|not_achieved` and its exact source/test
evidence, then separately with before/after hashes, changed
generator/source/test paths, disposition, normal/sanitizer receipts and counts,
contamination/family result, prompt-boundary result, and the strongest truthful
status. Run focused tests after each
generator change and proportional repository validation before handoff. Do not claim a dataset release or benchmark uplift.
