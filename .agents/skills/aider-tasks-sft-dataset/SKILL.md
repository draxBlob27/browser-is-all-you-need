---
name: aider-tasks-sft-dataset
description: Build and verify deterministic Aider whole-edit SFT train.jsonl projections from local generated task trees using the repo-owned w8-biayn CLI. Use when converting .w8-biayn/data/aider-tasks or aider-tasks-reverify roots into Aider-compatible SFT rows, matching an existing Aider task JSONL schema, excluding private .state controls, resolving task-ID collisions, or reconciling a generated projection with its source tasks.
---

# Aider Tasks SFT Dataset

Convert local Aider task roots through the repository command. Do not write a
one-off JSONL converter or hand-edit generated rows.

## Read first

1. Read `AGENTS.md` and `docs/AIDER_SFT_SCOPE.md`.
2. Inspect the requested source root and reference JSONL.
3. Read the repository implementation behind
   `w8-biayn data aider-tasks-sft` before changing conversion behavior.
4. Read
   `.agents/skills/audit-sft-data-quality/references/aider-fixed26-sft-improvement.md`
   when the projection is intended to improve Aider Polyglot C++ fixed-26 or a
   derivative benchmark with the same skill shape.
5. Keep source task trees immutable; change their owner if a task is wrong.

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

For the user-requested merge of expansion-v1 plus reverify local roots, use the
merged projection command instead of concatenating JSONL:

```bash
uv run w8-biayn data aider-tasks-sft build-merged \
  --expansion-root .w8-biayn/data/aider-tasks-expansion-v1 \
  --reverify-root .w8-biayn/data/aider-tasks-reverify \
  --reference .w8-biayn/data/aider-tasks-sft/sft/train.jsonl \
  --out .w8-biayn/data/aider-tasks-merged-sft
```

By default this excludes the invalidated historical
`reverify:aider-dsa/circular-buffer` duplicate subtree and keeps the newer
`reverify:aider-dsa/cyclic-slot-systems` replacement.

For a user-requested first-attempt projection, pass `--prompt-header-only`.
This keeps only C/C++ header files from `files.solution` in the user prompt
while preserving all `files.solution` to `files.example` outputs in the
assistant answer. Use a distinct sibling output root so repair-style and
first-attempt datasets do not overwrite each other:

```bash
uv run w8-biayn data aider-tasks-sft build \
  --tasks-root .w8-biayn/data/aider-tasks-expansion-v1 \
  --reference .w8-biayn/data/aider-tasks-sft/sft/train.jsonl \
  --out .w8-biayn/data/aider-tasks-expansion-v1-sft-header-only-YYYYMMDD \
  --prompt-header-only
```

## Verify

Always run verification after the last source or converter change:

```bash
uv run w8-biayn data aider-tasks-sft verify \
  --tasks-root .w8-biayn/data/aider-tasks-reverify \
  --reference .w8-biayn/data/aider-tasks-sft/sft/train.jsonl \
  --root .w8-biayn/data/aider-tasks-reverify-sft
```

For the merged projection:

```bash
uv run w8-biayn data aider-tasks-sft verify-merged \
  --expansion-root .w8-biayn/data/aider-tasks-expansion-v1 \
  --reverify-root .w8-biayn/data/aider-tasks-reverify \
  --reference .w8-biayn/data/aider-tasks-sft/sft/train.jsonl \
  --root .w8-biayn/data/aider-tasks-merged-sft
```

Header-only prompt projections record `prompt_file_mode: header-only` in the
manifest. `verify` and `verify-merged` infer that mode from the manifest by
default; pass `--prompt-header-only` when explicitly checking the intended mode.

Require all of the following before handoff:

- each discovered real task contributes exactly one row;
- merged projections record every source root and excluded source-prefix;
- every path containing `.state` is excluded, including adversarial controls;
- row and metadata key sets exactly match the reference;
- every row has one user message followed by one assistant message;
- no user prompt contains `.meta/`, `.state/`, or `CMakeLists.txt`;
- any allowlisted prompt sanitation is recorded per source in the manifest;
- labels and metadata task IDs match the unique row task ID;
- only colliding leaf IDs receive deterministic family qualification;
- the exact JSONL bytes, manifest inventory, source hashes, and reference hash
  recompute successfully.

If the projected dataset is presented as an Aider fixed-26 improvement batch,
also run or request an `$audit-sft-data-quality` pass against the exact
`sft/train.jsonl` and report the metrics from
`aider-fixed26-sft-improvement.md`: fixed-26 analog coverage, file-layout mix,
single-turn versus repair-trajectory share, duplicate instruction headers,
whole-edit parser pass rate, compile/test receipt coverage, context/token
length buckets, starter-to-answer copy ratios, and count-target fit. Require
the report to distinguish new benchmark-shaped rows/tasks from filtered current
synthetic anchors. A projection that remains header-only, single-turn, lacks
repair trajectories, falls below the minimum 1,000 new benchmark-shaped
rows/tasks without an explicit narrower experiment, or lacks per-row
compile/test receipts may still be a local projection, but must not be called
improvement-ready SFT data.

## Boundaries

- Treat this as a user-requested local projection, not a finalized dataset
  release, tokenizer/mask proof, training authorization, or benchmark claim.
- Do not use this converter to paper over source-corpus mismatch. If the source
  roots do not satisfy the fixed-26 improvement shape gates, return the
  limitation and route the fix through `aider-sft-task-creator` or
  `aider-task-family-remediation`.
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
uv run pytest -q tests/test_aider_sft_scope_docs.py
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py \
  .agents/skills/aider-tasks-sft-dataset
```
