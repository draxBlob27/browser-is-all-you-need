# Aider Benchmark SFT Task Roadmap

This branch is for Aider-benchmark-aligned C++ task creation, remediation,
audit evidence, and local SFT dataset construction.

## Current Focus

- Keep task specifications under `docs/aider-tasks-spec/` reviewable and
  aligned with the generated local task roots.
- Keep clean-room task-design and audit evidence under `docs/aider-synthetic/`.
- Keep local generated roots under `.w8-biayn/data/aider-tasks/`,
  `.w8-biayn/data/aider-tasks-reverify/`, and
  `.w8-biayn/data/aider-tasks-expansion-v1/`.
- Keep generated data and task roots out of Git.

## Completion Gates

Local task-family work ends at `local_family_verified`.

Before a family is considered locally complete, it needs:

- generator-owned regeneration;
- prompt-boundary and role validation;
- clean normal oracle evidence;
- fresh sanitizer oracle evidence when available;
- duplicate-family screening;
- benchmark-contamination screening;
- truthful audit/remedy records.

## Dataset Work

Dataset generation is limited to Aider-style SFT data and must stay tied to the
task roots and source evidence in this repository. Generated release bytes and
projection outputs remain local unless the user explicitly asks for an export.

## Branch Hygiene

Do not add model-training lanes, cloud launchers, benchmark runners,
observability adapters, legacy browser-agent stacks, or unrelated performance
experiments on this branch.

Keep branch guidance in:

- `docs/AIDER_BENCHMARK_SFT_TASK_BRANCH_SCOPE.md`
- `docs/AIDER_SFT_SCOPE.md`
- `.agents/REPO_GUIDE.md`
- relevant Aider skills under `.agents/skills/`
