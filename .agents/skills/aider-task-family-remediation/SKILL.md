---
name: aider-task-family-remediation
description: Create, audit, remediate, regenerate, and locally verify clean-room Aider-format C++ task families for future SFT use. Use when analyzing Aider Polyglot C++ weakness topics, authoring curriculum subtopics, implementing generated task families, writing remedy records, or improving tasks under docs/aider-synthetic and .w8-biayn/data/aider-tasks.
---

# Aider Task-Family Remediation

Use this skill for the local, clean-room task-family workflow. Its terminal
state is `local_family_verified`; it does not create SFT rows, train a model,
or claim benchmark uplift.

## Read first

1. `AGENTS.md`
2. `README.md`
3. `ROADMAP.md`
4. `docs/AIDER_SFT_SCOPE.md`
5. `docs/AIDER_TASK_MATERIALIZATION_GUIDE.md`
6. `docs/aider-tasks-spec/Original-specs.md`
7. `docs/aider-tasks-spec/verify-and-remedy.md`
8. The relevant curriculum, family specification, generator, focused tests, and
   generated family root.

Read `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md` only when the user
explicitly requests a dataset release. It is not a local-family completion gate.

## Prompt selection is mandatory

For **every** generated Aider task-family request, inspect
`docs/aider-tasks-spec/prompts/` before planning or changing files. A prompt
named by the user is mandatory. Otherwise select the prompt whose phase matches
the requested work:

- curriculum or family-spec authoring: `generate-family-spec.md`;
- implementation, regeneration, audit remediation, or verification of an
  existing family: `implement-family-for-sft.md`.

Read the selected prompt completely and follow it together with this skill,
`AGENTS.md`, and the normative family specification. Do not treat prompts as
balanced-tree-specific. If more than one prompt materially applies or their
instructions conflict, stop before making changes and ask the user which
workflow controls the request; do not silently combine or weaken them.

## Lifecycle

### 1. Find the weakness topic

Start from evidence about a model or benchmark weakness. Record the topic,
observed limitation, benchmark-holdout boundary, and a clean-room learning
objective. Do not copy an official Aider Polyglot task's wording, API, tests,
reference, or semantic contract.

Use `docs/aider-synthetic/` for the curriculum source document. A topic is not
a task until it has an observable, independently testable capability.

### 2. Define subtopics and curriculum roots

Split the topic into materially different subtopics. For each proposed root,
define a domain-specific API, state model, invalid/duplicate/absent behavior,
ordering/tie rules, examples, and a private property that distinguishes the
claimed implementation from a trivial substitute.

State the number of roots in the curriculum document as a planning inventory,
not a release quota. Do not retain roots that are renamed copies of one
algorithmic contract. Keep official benchmark roots and semantic copies out of
the curriculum.

### 3. Implement the curriculum through its owner

Find the owning generator/materializer under `src/w8_biayn/integrations/` and
its focused test under `tests/`. Change those sources, not generated files.

For each root, generate:

- visible docs plus exactly the declared editable files;
- an incomplete but coherent starter;
- an independent reference;
- visible and private deterministic tests;
- role-correct config/provenance and a reproducible CMake recipe.

Regenerate beneath `.w8-biayn/data/aider-tasks/`, or beneath the parallel
`.w8-biayn/data/aider-tasks-reverify/` root when preserving an existing family.
Never hand-edit that output. Never hand-edit either generated output.

### 4. Audit and write remedies

Use `docs/aider-tasks-spec/verify-and-remedy.md`. Before changing an existing
family, write its per-root remedy record and specification under the sibling
`.state/remedy/` location required by that document.

A remedy must identify the root cause, one disposition, public contract,
representation/invariant, forbidden substitutes, independent reference,
negative fixture, metadata roles, oracle commands, and benchmark/family screen.

Use `reject` for benchmark overlap or unverifiable provenance, `replace` for a
trivial or duplicate objective, and `repair-in-place` only when the objective
survives.

### 5. Remediate and locally verify

Implement the remedy in the generator, scaffold, or focused tests; regenerate
fresh output; then verify:

1. prompt and file-role boundaries expose only docs plus declared editable files;
2. references map to every editable file and private assets remain hidden;
3. normal and fresh ASan/UBSan reference builds have positive, equal discovery
   counts when the locked runtime is available;
4. private tests reject banned containers, sorted vectors, degenerate trees, or
   other named negative fixtures;
5. benchmark contamination and duplicate-family screening pass.

Record unavailable locked runtime prerequisites as `not_completed`; never
upgrade a host-only result to locked-oracle evidence. A family becomes
`local_family_verified` only when its required local gates pass.

### Toolchain and execution evidence

Run the owning generator's `--verify` mode before treating a generated family
as build-tested. It requires both `cmake` and `c++`; a focused Python
materialization test does not replace that oracle check.

Use host CMake for quick iteration only when its installation is a documented
machine prerequisite. If it is missing, record the exact missing command and
use the project's designated locked C++ image when one is available. Run that
image with networking disabled, record its immutable image identity, compiler,
CMake version, and verifier command, and let the generator regenerate its own
output. Do not introduce a shell wrapper, substitute ad-hoc compile commands,
or report a container result as locked-oracle evidence unless the family
specification designates that image as the locked grader.

If neither a documented host setup nor a designated C++ image is available,
leave normal/sanitizer evidence `not_completed`. Request the operator to
install the documented CMake prerequisite rather than attempting to bypass an
interactive privilege boundary.

## Guardrails

- Never modify generated task output by hand.
- Never create JSONL, token/mask evidence, splits, exports, or model-facing
  bundles in this workflow.
- Never claim SFT admission, training authorization, or benchmark uplift.
- Keep references, tests, metadata, CMake files, and receipts out of prompts.
- Update the curriculum/specification and focused regression test in the same
  logical change as the owning generator.
- Record the selected prompt path and any user-supplied inputs in the audit or
  remedy record so the workflow is reproducible.
- Treat an official Aider Polyglot C++ root as a permanent holdout.

## Handoff

Update the curriculum/specification with before/after tree hashes, changed
owner paths, remedy disposition, oracle receipt status/counts,
benchmark/family-screen result, prompt-boundary result, and the strongest
truthful local status. Future dataset construction must use a separate,
explicitly authorized intake process and may consume only
`local_family_verified` roots.

## Validation

Run the family’s focused tests, then:

```bash
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py \
  .agents/skills/aider-task-family-remediation
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

Also run the owning generator’s structural test and its normal/sanitizer
verifier when the required locked runtime is available.
