---
name: aider-sft-task-creator
description: Create new clean-room Aider-format C++ task families for future SFT use and orchestrate the mandatory create-audit-remediate-re-audit loop. Use when authoring a curriculum, implementing a new generated Aider task family, preparing local Aider SFT candidate roots, or driving those candidates through audit-sft-data-quality and aider-task-family-remediation until the exact regenerated family passes every applicable gate or has a truthful external blocker.
---

# Aider SFT Task Creator

Create new Aider-format C++ task families as generator-owned, executable,
evidence-bound candidates. Treat creation as the start of a closed quality
loop, never as admission by itself.

## Read first

Read these completely before changing behavior:

1. `AGENTS.md`
2. `README.md`
3. `ROADMAP.md`
4. `docs/AIDER_SFT_SCOPE.md`
5. `docs/AIDER_TASK_MATERIALIZATION_GUIDE.md`
6. `docs/aider-tasks-spec/Original-specs.md`
7. `docs/aider-tasks-spec/verify-and-remedy.md`
8. `.agents/skills/audit-sft-data-quality/SKILL.md`
9. `.agents/skills/aider-task-family-remediation/SKILL.md`
10. [references/iteration-contract.md](references/iteration-contract.md)
11. `.agents/skills/audit-sft-data-quality/references/aider-fixed26-sft-improvement.md`
    when the batch is intended to improve Aider Polyglot C++ fixed-26 or a
    derivative benchmark with the same skill shape

Inspect `docs/aider-tasks-spec/prompts/` and select
`generate-family-spec.md` for new curricula. Use
`implement-family-for-sft.md` when implementing the approved specification.
Read each selected prompt completely. Do not combine conflicting prompts.

Read `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md` only when the user has
explicitly authorized a dataset release. Local creation ends at verified task
roots; it does not authorize JSONL creation, export, training, or uplift claims.

For an Aider benchmark weakness-driven expansion, read the relevant checked-in
expansion specification, treat its aggregate count cells as binding, inventory
the existing reverify tree first, and write new roots only beneath
`.w8-biayn/data/aider-tasks-expansion-v1/`.

For a report-driven Aider fixed-26 improvement batch, the planning inventory
must also bind the eval-derived findings in
`aider-fixed26-sft-improvement.md`: prioritize answer-blind analogs for the
failed fixed-26 families, add first-try and repair variants for second-try-only
families, target about 2,000 new verified rows/tasks inside the 1,500-2,500
normal band, treat 1,000 new benchmark-shaped rows/tasks as the minimum useful
run, and split authoring into request batches of 40-100 new or improved roots.
Avoid a 100% header-only monoculture, and record file-layout, API-shape,
interaction-mode, family coverage, batch IDs, deferred backlog, and bucket
counts before materialization.

## Own the workflow

Use this state machine:

```text
design -> generate -> creator preflight -> independent audit
                                      audit pass -> complete
                                      findings   -> remediation -> regenerate
                                                               -> fresh audit
```

Continue the audit/remediation loop while an in-scope finding is repairable.
Do not declare success from the creator preflight or remediation verification;
only a fresh audit of the exact final tree closes the loop.

## 1. Design an executable contract

For every proposed root, define before writing the reference:

- a unique task ID and explicit new-root or replacement lineage;
- public C++17 API, inputs, outputs, owned state, and core mechanism;
- normal, invalid, duplicate, absent, boundary, ordering, and tie behavior;
- visible examples and private deterministic properties;
- forbidden generic or library substitutes;
- at least one coherent plausible-but-wrong implementation that must compile
  cleanly and be rejected by the production tests;
- clean-room provenance and benchmark-holdout separation.

Reject a proposal that is only a domain rename, constants/policy variant,
opposite-end variant, or semantic copy. Do not pad a requested root count with
weak roots.

When the target is Aider fixed-26 improvement, each root must name the held-out
skill family it analogizes and the specific benchmark behavior it teaches
without copying official wording, API identifiers, tests, filenames, task
labels, references, or executable contracts. Prefer Exercism-like C++ surfaces:
paired `.h`/`.cpp` edits, namespaces, classes with state over multiple calls,
exceptions, operators/free functions, exact string or matrix outputs, and
project-context files where the skill requires them. A header-only root may be
kept only when the planning inventory shows why it adds non-duplicate coverage.

## 2. Implement through a repository owner

Create or update the curriculum under `docs/aider-synthetic/`, then implement
the owning generator/materializer under `src/w8_biayn/integrations/` with
focused tests under `tests/`. Never hand-edit generated roots.

Generate each root with:

- visible docs and exactly declared editable starter files;
- complete private reference replacements for every editable file;
- visible and hidden deterministic tests;
- compiled coherent negative fixtures;
- C++17 CMake with strict warnings and offline dependencies;
- safe role metadata and provenance;
- reproducible normal and fresh ASan/UBSan verification.

Keep prompts free of references, tests, CMake, provenance, receipts, and hidden
assets. Avoid duplicated top-level instruction headers such as
`# Instructions`, repeated policy text, and unnecessary generated helper
boilerplate. Preserve raw proposals, generated candidates, rejected roots, and
selected roots as distinct artifacts.

For an expansion family, refuse `.w8-biayn/data/aider-tasks/` and
`.w8-biayn/data/aider-tasks-reverify/` as output roots. Before materialization,
reject task-ID or semantic-lineage overlap with either existing tree. A failed
existing root is remediation input, not a new task to recreate under another
slug.

## 3. Run creator preflight

Before audit handoff, require all applicable checks to pass on the exact tree:

- owner regeneration and focused structural tests;
- prompt/role and whole-file response boundary validation;
- positive and equal normal/sanitizer test discovery;
- reference pass in the mandatory network-disabled Docker sanity or designated
  locked image;
- execution and rejection of every coherent wrong substitute;
- whole-family seven-dimension diversity screen and adversarial clone controls;
- benchmark contamination, semantic overlap, task-ID, prompt-hash,
  answer/reference-hash, and lineage-conflict screens;
- duplicate instruction-header scan and file-layout/interaction-mode summary
  when the roots feed an Aider fixed-26 improvement batch;
- fixed-26 bucket-count ledger for new failed-family analogs, second-try-only
  family variants, multi-file API discipline tasks, repair-support evidence,
  and filtered current synthetic anchors when the batch feeds SFT;
- request-batch ledger showing 40-100 included new/improved roots unless the
  explicit scope is smaller, plus deferred backlog and prior-batch overlap
  checks;
- a receipt binding owner, tree, contract, prompt, starter, reference, tests,
  image/compiler, policy, and result digests.

A missing prerequisite is `not_completed`. A plausible task or host-only build
is not a pass. Any content, owner, grader, or policy change invalidates prior
receipts.

## 4. Hand off to independent audit

After preflight, load and apply `$audit-sft-data-quality` as a read-only audit
of the raw exact artifacts. Do not give the audit an intended verdict. Provide
the contract, manifests, roots, receipts, source inventory, and holdout
inventory—not the creator's confidence or desired result.

Require a row/root catalog, evidence-backed findings, duplicate and lineage
report, contamination report, corpus composition, and explicit dispositions.
Record the audit subject hash and immutable report path before any repair.

Audit success means every retained root passes every applicable hard gate and
the family/corpus gates pass. It does not mean dataset release or training is
authorized.

## 5. Route findings to remediation

If the audit reports any defect, ambiguity, stale evidence, collision,
contamination risk, or missing gate:

1. Preserve the audit report unchanged and assign stable finding IDs.
2. Load and apply `$aider-task-family-remediation`.
3. Map each finding to `repair-in-place`, `replace`, or `reject` with a remedy
   record. Do not silently drop findings.
4. Fix the curriculum, owner, scaffold, or focused tests—not generated output.
5. Regenerate the complete affected family and rerun remediation verification.
6. Mark the prior audit and receipts stale because they bind the old tree.
7. Return the new exact tree and all finding dispositions to a fresh
   `$audit-sft-data-quality` pass.

If a rejected root makes a user-required count short, author a genuinely new
backfill root and send it through the complete creation and audit loop.

## 6. Close only on a clean fresh audit

Finish only when the newest audit binds the current exact tree and reports:

- zero unresolved hard-gate findings;
- zero retained review, repair, conflict, or contamination dispositions;
- all rejected/replaced roots absent from the retained candidate manifest;
- current normal, sanitizer, negative-fixture, prompt-boundary, diversity, and
  lineage evidence;
- requested root-count bounds satisfied by passing roots only;
- truthful terminal status no stronger than `local_family_verified` under the
  current repository scope.

If Docker, a designated image, a source contract, or required authority remains
unavailable after safe in-scope checks, stop with `not_completed`, name the
exact blocker, and preserve the loop state for resumption. Never weaken a gate
to force convergence.

## Handoff

Report the final tree and owner paths, cycle count, audit subject hash, closed
finding IDs, rejected/replaced roots, current receipt locations, exact passing
root count, and strongest truthful status. State explicitly that no SFT release,
training authorization, or benchmark uplift follows from local completion.

## Validate this skill

After changing this skill, run:

```bash
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py \
  .agents/skills/aider-sft-task-creator
python3 /home/ubuntu/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  .agents/skills/aider-sft-task-creator
uv run pytest -q tests/test_aider_sft_scope_docs.py
```
