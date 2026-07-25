# Repository Development Guide

`AGENTS.md` and `CLAUDE.md` must stay symlinks to this file. Update this file
once; do not fork the guidance.

## Active Branch

This branch is scoped to Aider-benchmark-aligned C++ task creation, local task
family remediation, audit evidence, and local SFT row projection for the
in-repository generated Aider task roots.

Do not use this branch for model-training lanes, cloud launchers, benchmark
runners, observability plumbing, legacy browser-agent stacks, or unrelated
performance experiments. Those surfaces belong on separately scoped branches.

## Required Reading

Before changing behavior, read:

1. `README.md`
2. `ROADMAP.md`
3. `docs/AIDER_BENCHMARK_SFT_TASK_BRANCH_SCOPE.md`
4. `docs/AIDER_SFT_SCOPE.md` when implementing or changing a local generated
   Aider task family
5. The relevant skill under `.agents/skills/`

## In Scope

- Task specifications, audits, remedies, and prompts under
  `docs/aider-tasks-spec/`.
- Clean-room Aider task design and audit records under `docs/aider-synthetic/`.
- Skills that directly govern Aider task creation, independent SFT-data audit,
  task-family remediation, expansion remediation, and branch cleanup.
- Small helper scripts whose only purpose is auditing, planning, or closing
  Aider task-spec remediation cycles.
- Local generated task roots under `.w8-biayn/data/aider-tasks/`,
  `.w8-biayn/data/aider-tasks-reverify/`, and
  `.w8-biayn/data/aider-tasks-expansion-v1/`.

The three local task roots are intentionally not pushed to Git.

## Local Aider Task-Family Remediation

Use `.agents/skills/aider-task-family-remediation/SKILL.md` for clean-room
Aider task creation, curriculum implementation, task audit, and remediation.
That skill owns the path from benchmark weakness topic through regenerated
local task roots and final local verification.

It ends at
`local_family_verified`.

Local remediation does not require dataset release rows, tokenizer or mask
proof, split finalization, training authorization, or benchmark uplift claims.

New expansion roots must inventory existing generated trees, must never
overwrite, copy, or rename an existing task, and must pass the prompt-boundary,
role, oracle, contamination, and duplicate-family gates described in
`docs/AIDER_SFT_SCOPE.md`.

## Data Discipline

Generated task roots and generated SFT projections remain local unless a user
explicitly asks for an export artifact. Do not commit `.w8-biayn/`, generated
datasets, task build trees, caches, virtual environments, logs, credentials, or
run artifacts.

If a task-family workflow needs repeated commands or checks, keep the helper
script focused on Aider task creation or remediation. Do not add generic model
training, evaluation, cloud, or monitoring adapters on this branch.

## Tests

Run the narrowest tests that cover the change. For scope and local Aider
workflow changes, prefer:

```bash
uv run pytest -q tests/test_aider_sft_scope_docs.py
uv run pytest -q tests/test_docs_guardrails.py
```

If code under `src/w8_biayn/aider_sft/` changes, also run the relevant
`tests/test_aider_sft_pipeline.py` cases.
