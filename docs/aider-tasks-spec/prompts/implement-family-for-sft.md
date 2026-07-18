# Implement a Local Aider Task Family Until It Is Verified

Inputs (the only inputs you will receive):

```text
TASK_FAMILY_ROOT=<absolute-or-repo-relative task-family directory>
SPEC_DOCUMENT_PATH=<absolute-or-repo-relative deterministic family specification>
```

Implement the family described by `SPEC_DOCUMENT_PATH`; use
`TASK_FAMILY_ROOT` as its generated/local artifact location. Discover all other
paths from the repository.

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
2. Create the per-root remediation records/specifications and obey the
   disposition/state-machine rules in `verify-and-remedy.md`.
3. Never hand-edit generated task output. Change the owning generator,
   scaffold, config, renderer, and focused tests, then regenerate the family.
4. Implement every specified API, starter, independent reference, invariant,
   forbidden-substitute rule, public/private test, metadata/provenance field,
   CMake/Catch setting, and verifier receipt.
5. Add negative fixtures showing the prior trivial/template implementation
   fails. Renaming or a happy-path test is not a remedy.
6. Keep private references/tests/provenance/CMake/receipts out of prompts.
7. Run the strongest available normal and fresh ASan/UBSan reference verification,
   recording missing runtime prerequisites rather than inferring a result.
8. Run semantic/slug benchmark-contamination and duplicate/family screening.
   Reject or replace required roots; never waive a near-match by renaming.
9. Do not create one-off JSONL or claim a dataset release from local artifacts.
10. Mark a family `local_family_verified` only after regeneration, prompt-boundary
    validation, normal/sanitizer evidence, and benchmark/family screening pass.
    Do not claim a dataset release.

For every root, update the audit/specification with before/after hashes,
changed generator/source/test paths, disposition, normal/sanitizer receipts and
counts, contamination/family result, prompt-boundary result, and the strongest
truthful status. Run focused tests after each
generator change and proportional repository validation before handoff. Do not claim a dataset release or benchmark uplift.
