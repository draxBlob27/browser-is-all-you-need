# Current Aider Task-Authoring Scope

## Authority

This document defines the current scope for Aider-style C++ task authoring in
this repository. It supersedes active-scope statements in older Aider SFT
planning documents. It does not declare a dataset release, training run, or
benchmark uplift.

## In scope

Current work is limited to these four local surfaces:

- `.w8-biayn/data/aider-tasks/` — generated local Aider-format task artifacts.
- `.w8-biayn/data/aider-tasks-reverify/` — parallel generated
  re-verification artifacts. These preserve the corresponding legacy family
  under `.w8-biayn/data/aider-tasks/`.
- `.w8-biayn/data/aider-tasks-expansion-v1/` — new Aider benchmark
  weakness-driven roots governed by the checked-in expansion task plans. This
  is a sibling output tree and may not overwrite, copy, or rename tasks from
  either existing generated tree.
- `docs/aider-synthetic/` — their clean-room curriculum and task-design
  documents.

The owner of a generated artifact is its repository generator or materializer.
Change that owner and regenerate the appropriate output tree; never hand-edit
a task beneath any generated-artifact root.

New curricula and task families must use the repository's
`aider-sft-task-creator` skill. Creation produces candidates only. Each exact
generated tree must then receive a read-only `audit-sft-data-quality` pass; all
findings route through `aider-task-family-remediation`, owner-controlled
regeneration, and a fresh audit. Repeat until the current exact tree receives a
clean audit or a concrete prerequisite is recorded as `not_completed`. Neither
creator preflight nor remediation self-verification may close this loop.

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

No projection command is currently shipped. A future user-authorized projection
must be implemented as a narrow, owner-controlled tool and must exclude `.state`
paths, private markers, duplicate task identities, and task-contract rewrites.
It must write only beneath an ignored sibling output root and record its exact
source roots in a manifest.

A separately scoped future projection may create only a local `sft/train.jsonl`
and its manifest. It does not establish dataset-release readiness, token/mask
evidence, split approval, training authorization, or benchmark uplift. Any of
those stages requires a separate request and its applicable verification.

## Out of scope

Repository-wide Aider release profiles, fixed root quotas, source inventories,
release-bound provider overlays, readiness bundles, release exports,
specialized consumer adapters, and their `data aider-sft` CLI instructions are
retired. No cloud-backed or provider-backed authoring command is active on this
branch.

If a future change needs dataset admission, its owner must first publish a new
approved admission contract that explicitly names these local task roots and
their required evidence. That contract must be fail-closed: it must require an
executable behavioral contract and deterministic assertions, an independently
verified reference under the locked build/test/sanitizer policy, an executed
plausible-but-wrong discriminator, digest-bound task and environment lineage,
and a corpus-wide duplicate/conflict/contamination screen before any merge.
Changed prompt, target, reference, tests, generator, or environment invalidate
prior evidence. Same-ID revisions remain quarantined until independently
verified and cannot coexist with a trusted ancestor as active targets. Until
then, retain the benchmark-holdout and clean-room boundaries in the task
specifications.

## Checklist

- [ ] The curriculum document is under `docs/aider-synthetic/`.
- [ ] New task families used `aider-sft-task-creator` and preserve an
      append-only creation/audit/remediation cycle record.
- [ ] The owning generator/materializer, not generated output, was changed.
- [ ] The family was regenerated beneath the appropriate generated-artifact
      root; re-verification preserves its legacy family under
      `.w8-biayn/data/aider-tasks/`.
- [ ] Public prompts exclude references, tests, metadata, build files, and
      receipts.
- [ ] Documentation describes the task as local candidate material, not an SFT
      release or benchmark result.
- [ ] Each proposed root has an executable contract, an executed
      plausible-but-wrong discriminator, and digest-bound normal/sanitizer
      reference evidence before it can be considered for any future intake.
- [ ] Candidate, selected, replaced, and rejected records stay separate; a
      same-ID revision is quarantined until its own evidence is complete.
- [ ] The final status is backed by a fresh `audit-sft-data-quality` pass over
      the exact post-remediation tree, with zero unresolved hard-gate findings.
- [ ] Any future admission work has a replacement approved contract before it
      creates rows or claims readiness.
