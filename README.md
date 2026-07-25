# w8-biayn

This branch is for Aider-benchmark-aligned C++ task creation, task-family
remediation, audit evidence, and local SFT row-projection planning.

It is not the active home for model-training lanes, cloud launchers,
observability plumbing, general benchmark runners, or unrelated performance
experiments. Generated task roots stay local and are not pushed to Git.

## Branch Scope

In scope:

- Task specifications, audits, remedies, and prompts under
  `docs/aider-tasks-spec/`.
- Clean-room Aider task design and audit evidence under `docs/aider-synthetic/`.
- Skills for Aider task creation, remediation, SFT-data audit, expansion
  remediation, and branch cleanup under `.agents/skills/`.
- Small helper scripts that audit, plan, or close Aider task-spec remediation
  cycles.
- Local generated task roots under `.w8-biayn/data/aider-tasks/`,
  `.w8-biayn/data/aider-tasks-reverify/`, and
  `.w8-biayn/data/aider-tasks-expansion-v1/`.

Out of scope unless a user explicitly asks for a separately scoped exception:

- Training lanes and model evaluation wrappers.
- Cloud launchers and remote benchmark runners.
- Dataset release readiness, tokenizer or mask ledgers, final train/validation
  splits, training authorization, or benchmark uplift claims.
- Generated datasets, caches, run logs, credentials, model artifacts, and local
  build output.

See `docs/AIDER_BENCHMARK_SFT_TASK_BRANCH_SCOPE.md` for the source-of-truth
branch boundary.

## Local Task Roots

The only local `.w8-biayn/data` roots expected for this branch are:

```text
.w8-biayn/data/aider-tasks
.w8-biayn/data/aider-tasks-expansion-v1
.w8-biayn/data/aider-tasks-reverify
```

These directories are local working data. They should stay untracked.

## Aider Task Workflow

Use `.agents/skills/aider-task-family-remediation/SKILL.md` for clean-room
Aider task creation, task audit, remediation, regeneration, and local
verification.

Local family work ends at `local_family_verified`. It does not require dataset
release artifacts, token or mask proof, train/validation split finalization, or
training evidence.

For new task-family creation, use
`.agents/skills/aider-sft-task-creator/SKILL.md`. For independent data-quality
review, use `.agents/skills/audit-sft-data-quality/SKILL.md`.

## Local projection boundary

No repository-wide dataset, release, tokenizer, consumer-export, cloud, or
benchmark-runner CLI is provided on this branch. Generated outputs must remain
under ignored local roots unless a separately scoped request adds an
owner-controlled projection tool.

## Validation

For branch-scope and README changes, run:

```bash
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

For Python package changes, also run:

```bash
uv run python -m compileall src/w8_biayn
```
