# Current Aider Task-Authoring Scope

## Authority

This document defines the current scope for Aider-style C++ task authoring in
this repository. It supersedes active-scope statements in older Aider SFT
planning documents. It does not declare a dataset release, training run, or
benchmark uplift.

## In scope

Current work is limited to these three local surfaces:

- `.w8-biayn/data/aider-tasks/` — generated local Aider-format task artifacts.
- `.w8-biayn/data/aider-tasks-reverify/` — parallel generated
  re-verification artifacts. These preserve the corresponding legacy family
  under `.w8-biayn/data/aider-tasks/`.
- `docs/aider-synthetic/` — their clean-room curriculum and task-design
  documents.

The owner of a generated artifact is its repository generator or materializer.
Change that owner and regenerate the appropriate output tree; never hand-edit
a task beneath either generated-artifact root.

## Local-family completion

A local family is complete at `local_family_verified` when its owning generator
has regenerated it, its prompt/role boundary is valid, its reference has the
strongest available normal and fresh ASan/UBSan evidence, and its
benchmark-contamination and duplicate-family screens pass. There is no fixed
root-count gate for local-family completion. Record an unavailable locked
runtime as `not_completed`; do not infer a pass from a host build.

## Current status

These task roots are candidate authoring and verification material only. Their
metadata must continue to state the strongest evidence actually available.
They are not SFT rows, a finalized dataset, a training authorization, or
benchmark-uplift evidence. References, hidden tests, provenance, CMake files,
and receipts remain private to each task root.

## User-authorized local SFT projection

The explicitly requested projection from
`.w8-biayn/data/aider-tasks-reverify/` is the narrow exception to the default
no-row authoring boundary. Its owner is
`w8-biayn data aider-tasks-sft build|verify`, implemented in
`src/w8_biayn/integrations/moonlight_aider_tasks_sft.py`. It must match the row
shape of `.w8-biayn/data/aider-tasks-sft/sft/train.jsonl`, exclude every
`.state` path, include each real discovered task once, qualify colliding leaf
IDs deterministically, and write only beneath the sibling
`.w8-biayn/data/aider-tasks-reverify-sft/` output. User prompts must reject
private path markers. The sole current sanitation is the named, manifest-bound
balanced-tree owner-spec appendix; no general task-contract rewriting is
allowed.

This exception authorizes the local `sft/train.jsonl` projection and its
manifest only. It does not establish dataset-release readiness, token/mask
evidence, split approval, training authorization, or benchmark uplift. Any of
those stages requires a separate request and its applicable verification.

## Out of scope

The repository-wide `aider_sft` pipeline, its profiles, source inventories,
release bundles, exports, and associated CLI instructions are historical
surfaces for the current task-authoring effort. Do not use them as active
requirements or claim their release status while working on the three in-scope
directories above.

If a future change needs dataset admission, its owner must first publish a new
approved admission contract that explicitly names these local task roots and
their required evidence. Until then, retain the benchmark-holdout and
clean-room boundaries in the task specifications.

## Checklist

- [ ] The curriculum document is under `docs/aider-synthetic/`.
- [ ] The owning generator/materializer, not generated output, was changed.
- [ ] The family was regenerated beneath the appropriate generated-artifact
      root; re-verification preserves its legacy family under
      `.w8-biayn/data/aider-tasks/`.
- [ ] Public prompts exclude references, tests, metadata, build files, and
      receipts.
- [ ] Documentation describes the task as local candidate material, not an SFT
      release or benchmark result.
- [ ] Any future admission work has a replacement approved contract before it
      creates rows or claims readiness.
