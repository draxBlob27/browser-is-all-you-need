---
name: aider-tasks-sft-dataset
description: Build and verify deterministic Aider whole-edit SFT train.jsonl projections from local generated task trees using the repo-owned w8-biayn CLI. Use when converting .w8-biayn/data/aider-tasks or aider-tasks-reverify roots into Moonlight-style SFT rows, matching an existing Aider task JSONL schema, excluding private .state controls, resolving task-ID collisions, or reconciling a generated projection with its source tasks.
---

# Aider Tasks SFT Dataset

Convert local Aider task roots through the repository command. Do not write a
one-off JSONL converter or hand-edit generated rows.

## Read first

1. Read `AGENTS.md` and `docs/AIDER_SFT_SCOPE.md`.
2. Inspect the requested source root and reference JSONL.
3. Read
   `src/w8_biayn/integrations/moonlight_aider_tasks_sft.py` before changing
   conversion behavior.
4. Keep source task trees immutable; change their owner if a task is wrong.

## Build

Use the corrected reference-shaped projection command:

```bash
uv run w8-biayn data aider-tasks-sft build \
  --tasks-root .w8-biayn/data/aider-tasks-reverify \
  --reference .w8-biayn/data/aider-tasks-sft/sft/train.jsonl \
  --out .w8-biayn/data/aider-tasks-reverify-sft
```

Pass `--force` only when the user explicitly requests regeneration of a
different existing output. The command writes `sft/train.jsonl` plus a manifest
that binds the reference contract, source inventory, source hashes, counts, and
output hash.

## Verify

Always run verification after the last source or converter change:

```bash
uv run w8-biayn data aider-tasks-sft verify \
  --tasks-root .w8-biayn/data/aider-tasks-reverify \
  --reference .w8-biayn/data/aider-tasks-sft/sft/train.jsonl \
  --root .w8-biayn/data/aider-tasks-reverify-sft
```

Require all of the following before handoff:

- each discovered real task contributes exactly one row;
- every path containing `.state` is excluded, including adversarial controls;
- row and metadata key sets exactly match the reference;
- every row has one user message followed by one assistant message;
- no user prompt contains `.meta/`, `.state/`, or `CMakeLists.txt`;
- any allowlisted prompt sanitation is recorded per source in the manifest;
- labels and metadata task IDs match the unique row task ID;
- only colliding leaf IDs receive deterministic family qualification;
- the exact JSONL bytes, manifest inventory, source hashes, and reference hash
  recompute successfully.

## Boundaries

- Treat this as a user-requested local projection, not a finalized dataset
  release, tokenizer/mask proof, training authorization, or benchmark claim.
- Do not expose tests, receipts, provenance, CMake files, or `.state` content in
  user prompts. Reference files appear only in assistant targets.
- The converter may remove only its audited, named balanced-tree owner-spec
  appendix. Fail closed on every other private-path leak; do not generalize
  sanitation into silently rewriting task contracts.
- Do not create validation/test splits, token ledgers, exports, or run training
  unless the user separately requests and authorizes those stages.
- Fail closed when the reference is missing or malformed, a source file is
  missing, task IDs remain ambiguous, or verification differs from current
  source bytes.

## Validation after code changes

```bash
uv run pytest -q tests/test_moonlight_aider_tasks_sft.py
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py \
  .agents/skills/aider-tasks-sft-dataset
```
