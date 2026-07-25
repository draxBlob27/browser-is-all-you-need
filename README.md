# w8-biayn

This branch is for Aider-benchmark-aligned C++ task creation, task-family
remediation, audit evidence, and local SFT data construction.

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

## CLI

The branch keeps a narrow `w8-biayn` CLI for Aider SFT task utilities:

```bash
uv run w8-biayn scope
uv run w8-biayn data aider-sft --help
```

Generated outputs must be written under ignored local roots unless a user
explicitly requests a specific export artifact.

## Preserved GLM/Modal Aider Base-Eval Context

The following GLM/Modal Aider Polyglot C++ base-eval notes are retained as
historical benchmark context. They are not the active branch workflow, and the
Modal implementation files are not part of this branch after cleanup.

The optional benchmark ran the base `zai-org/GLM-4.7-Flash` checkpoint against
the C++ subset of `Aider-AI/polyglot-benchmark` through Aider's own benchmark
harness. Modal hosted one four-H100 SGLang server plus a CPU Aider runner. It
was neither a SLIME lane nor the custom Polyglot evaluator, and Aider's
cumulative `pass_rate_2` after a repair turn must not be called pass@2.

The historical operator entrypoint was:

```bash
bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

That path is intentionally not present on this branch. Recover it from the
appropriate historical branch or commit before attempting to run that eval.

The historical contract was export-only, defaulted to a redacted no-spend plan,
required explicit paid acknowledgement for smoke/full, gated full behind the
real two-task smoke, persisted official Aider artifacts in a Modal Volume and
ignored local state, and verified the ephemeral App stopped before admitting a
result. Source and offline tests existed, while paid validation and the first
complete 26-task receipt were pending.

The distinct `independent-pass-at-1-and-8` result family used eight independent
trajectories per task with up to two sequential Aider tries inside each
trajectory. It reported exactly `pass@1_try1`, `pass@1_try2`, `pass@8_try1`,
and `pass@8_try2`; try 2 could consume feedback only from its own try 1.

Operational notes retained from that lane:

- Paid acknowledgements were launch safety gates, not immutable result
  identity.
- The sampling smoke pinned `binary-search-tree` and `grade-school` for all
  eight trajectories and stored corrected proof under `sampling-smoke-v1`.
- Independent full runs required `W8_MODAL_AIDER_MAX_RUN_SECONDS=14400`.
- Aider's `num_exhausted_context_windows` recorded provider
  `finish_reason=length` output-limit events and was diagnostic only.
- `runner.identity.json` bound immutable config to one Modal App so worker
  restart could re-enter without treating its own artifacts as stale.
- Explicit resume reused only samples with complete official rows plus
  `stats.json`, archived interrupted samples under `incomplete-attempts/`, and
  preserved prior local failure downloads under `resume-download-archives/`.

## Validation

For branch-scope and README changes, run:

```bash
uv run pytest -q tests/test_aider_sft_scope_docs.py
```

For Python package changes, also run:

```bash
uv run python -m compileall src/w8_biayn
```
