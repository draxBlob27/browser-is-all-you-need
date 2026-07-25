# Aider Benchmark SFT Task Branch Scope

This branch is scoped to Aider-benchmark-aligned C++ task creation, task
remediation, audit evidence, and local SFT row projection for the in-repository
Aider task roots.

## In scope

- Task specifications, audits, remedies, and prompts under
  `docs/aider-tasks-spec/`.
- Clean-room Aider task design and audit records under `docs/aider-synthetic/`.
- Skills that directly govern Aider task creation, independent SFT-data audit,
  task-family remediation, and expansion-v1 remediation.
- Small helper scripts whose only purpose is auditing, planning, or closing
  Aider task-spec remediation cycles.
- Local generated task roots under `.w8-biayn/data/aider-tasks/`,
  `.w8-biayn/data/aider-tasks-reverify/`, and
  `.w8-biayn/data/aider-tasks-expansion-v1/`. These roots are intentionally
  local and are not pushed to Git.

## Out of scope for this branch

- SLIME, Moonlight, GLM, PIE, GRPO, Modal, W&B, SkyRL, rLLM, cloud launchers,
  training lanes, benchmark runners, model evaluation wrappers, and their
  tests/docs/skills.
- Dataset release readiness, tokenizer or mask ledgers, final train/validation
  splits, training authorization, or benchmark uplift claims.
- Any converter, launcher, or adapter that exists primarily for a model
  training or evaluation lane rather than Aider task construction.

When a change touches both an Aider task surface and one of the excluded
surfaces, split the work. Commit only the Aider task portion on this branch and
leave excluded-surface changes unstaged, restored, or moved to a branch that is
explicitly scoped for that work.
