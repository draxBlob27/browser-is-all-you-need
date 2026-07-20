---
name: w8-biayn-framework
description: "Maintain, extend, test, document, and operate w8-biayn C++ performance-RL and local Aider task-family remediation workflows. Use for SLIME, Moonlight, GLM, PIE, clean-room Aider task curricula, generated task remediation, C++ reward/eval, repo guidance, or legacy boundaries."
---

# w8-biayn Framework

Use this skill for work in this repository. Keep workflows reproducible from a
fresh clone and prefer repo-owned commands/wrappers over one-off shell history.

## Source Of Truth

Read these before changing behavior:

1. `AGENTS.md`
2. `README.md`
3. `ROADMAP.md`
4. `docs/AIDER_SFT_SCOPE.md` for local Aider task-family work; read
   `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md` only for an explicitly
   authorized dataset release
5. Relevant code under `src/w8_biayn/`

If `/tmp/ENGINEERING_SPEC_v2_cpp_only.md` exists, it may provide historical
context, but checked-in guidance is the active source of truth.

## Active Goal

- Build runnable C++ optimization tasks from official PIE.
- Convert admitted tasks into SLIME SFT, GRPO, and eval JSONL.
- Train Moonlight and GLM lanes with SLIME, Megatron, and SGLang.
- Reward generated C++ by response format, compile/sanitizer correctness,
  visible and hidden tests, and child-process CPU-time runtime efficiency.
- Evaluate base, SFT, and GRPO outputs on held-out PIE tasks and prove uplift.

## Hard Boundaries

Do not write a custom trainer.

Do not use PIE's old Hugging Face Trainer path or any SuperCoder trainer as the
active trainer.

Do not reintroduce SkyRL/rLLM as the active training stack unless the user
explicitly asks for legacy maintenance or rollback.

Allowed upstream use:

- SLIME: active SFT/GRPO framework.
- PIE: C++ `v0 -> v1` data, official tests, and eval/data lessons.
- LearningOpt PIE: gem5 reference/calibration lessons when relevant.
- SuperCoder: schema, correctness, and eval lessons only.
- SkyRL/rLLM: legacy reference only.

Use `uv run w8-biayn upstreams clone` for pinned upstream copies under
`.cache/upstreams/`. Temporary study clones may live under `/tmp`; do not vendor
upstream repos or data.

SLIME, Megatron, and SGLang are the active training stack. Enter the generated
SLIME container through `.w8-biayn/slime/run-container.sh` and use the
repo-owned lane wrappers. SkyRL/rLLM paths are legacy reference only and must
not be restored as the active path without an explicit rollback request.

## Local Aider Task-Family Workflow

For clean-room Aider task creation, curriculum implementation, task audit, or
remediation, use `.agents/skills/aider-task-family-remediation/SKILL.md`. It
owns the path from benchmark weakness topic through regenerated local task
roots and `local_family_verified`, including the distinction between host CMake
iteration and image-bound normal/ASan/UBSan evidence. It also requires generic
workflow-prompt selection from `docs/aider-tasks-spec/prompts/`, rather than a
balanced-tree-only prompt path. It does not create SFT rows or release artifacts.

## Active Repository Map

- Historical Aider dataset-release specification:
  `docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`
- Historical Aider dataset-release implementation: `src/w8_biayn/aider_sft/`
- Historical Aider profiles and manifests: `configs/aider_sft/` and
  `manifests/aider_sft/`
- Historical Aider pipeline tests: `tests/test_aider_sft_pipeline.py`
- Bootstrap: `scripts/bootstrap.sh`
- CLI: `src/w8_biayn/cli.py`
- Dataset setup and manifests: `src/w8_biayn/cpp_perf/data.py`
- Coverage measurement: `src/w8_biayn/cpp_perf/coverage.py`
- PIE parsing/task construction: `src/w8_biayn/cpp_perf/pie.py`
- SLIME dataset conversion: `src/w8_biayn/cpp_perf/slime_dataset.py`
- Contest-style output judging: `src/w8_biayn/cpp_perf/judge.py`
- Task schema: `src/w8_biayn/cpp_perf/schema.py`
- Prompt/SFT helpers: `src/w8_biayn/cpp_perf/prompts.py`
- Reward and sandbox: `src/w8_biayn/cpp_perf/reward.py`,
  `src/w8_biayn/cpp_perf/sandbox.py`
- Eval aggregation: `src/w8_biayn/cpp_perf/eval.py`
- SLIME setup/doctor/sandbox helpers: `src/w8_biayn/slime_integration/`
- SLIME C++ bridge: `src/w8_biayn/integrations/slime_cpp_perf.py`
- SLIME Polyglot C++ bridge: `src/w8_biayn/integrations/slime_polyglot_cpp.py`
- Official Aider/Modal C++ contract: `src/w8_biayn/modal_aider_polyglot_cpp.py`
- Official Aider/Modal operator lane:
  `examples/modal/glm47_flash_aider_polyglot_cpp/`
- Offline Modal/Aider regression tests: `tests/test_modal_aider_polyglot_cpp.py`
- SLIME Multi-SWE C++ bridge: `src/w8_biayn/integrations/slime_multi_swe_cpp.py`
- W&B reporting layer (metrics/tables/artifacts/alerts/workspace):
  `src/w8_biayn/wandb_report.py`
- Network reachability probes + launch watchdog: `src/w8_biayn/net_health.py`
- Regression lints (one guard per paid incident):
  `tests/test_regression_lints.py`
- Pipeline milestone logger (standalone, host+container):
  `scripts/wandb_milestone.py`
- SLIME train entry wrapper:
  `src/w8_biayn/integrations/slime_train_entry.py`
- Moonlight HF export shim:
  `src/w8_biayn/integrations/slime_moonlight_hf_export.py`
- Moonlight Megatron local layer spec: `src/local.py`
- Moonlight C++ lane: `examples/slime/moonlight_cpp_perf/`
- Moonlight Multi-SWE C++ base-eval lane: `examples/slime/moonlight_multi_swe_cpp/`
- Moonlight rank-16 LoRA C++ lane: `examples/slime/moonlight_lora_cpp_perf/`
- GLM C++ lane: `examples/slime/glm47_cpp_perf/` when present
- GLM agentic SWE-agent file-state C++ lane: `examples/slime/glm47_swe_agent_cpp_perf/`
- ReTool lane: `examples/slime/retool/`
- Moonlight MoE smoke: `examples/slime/moonlight_moe_smoke/`

The old SkyRL/rLLM/GCP control-plane modules were removed from this branch and
remain available in git history. Thin CLI shims may still report that a legacy
surface is unavailable. Do not recreate or extend those modules unless the
task explicitly asks for rollback or legacy compatibility work.

## Required User Path

A clean clone should support:

```bash
./scripts/bootstrap.sh
uv run w8-biayn data doctor
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime doctor
uv run w8-biayn slime setup
uv run w8-biayn cpp harness preflight --dry-run
```

If a change breaks this path, update code, tests, README, AGENTS/CLAUDE, and
this skill together.

## Data Workflow

No one-off dataset munging. Every conversion or cleanup must be a CLI-backed
project command or repo-owned script.

Build official PIE task JSON:

```bash
RUN_ID="r$(date -u +%Y%m%d%H%M%S)"
uv run w8-biayn data pie download --out .w8-biayn/data/pie
uv run w8-biayn data pie prepare-full --source-root .w8-biayn/data/pie --out .w8-biayn/data/pie-full --force
uv run w8-biayn data pie measure-coverage --prepared-root .w8-biayn/data/pie-full --out .w8-biayn/data/pie-full/coverage.json --report-out .w8-biayn/data/pie-full/coverage-report.json
uv run w8-biayn data pie build-full-tasks --prepared-root .w8-biayn/data/pie-full --coverage-json .w8-biayn/data/pie-full/coverage.json --out .w8-biayn/data/tasks-full --min-train 1000 --min-validation 100 --min-test 100 --force
uv run w8-biayn data skyrl build --tasks-dir .w8-biayn/data/tasks-full --out .w8-biayn/data/skyrl-full --profile full-official --run-id "$RUN_ID" --min-train-tasks 1000 --min-validation-tasks 100
# Optional explicit SLIME C++ lane; keep prompt-only JSONL plus task metadata for the SLIME reward hook.
uv run w8-biayn data slime build --tasks-dir .w8-biayn/data/tasks-full --out .w8-biayn/data/slime-pie --profile full-official --run-id "$RUN_ID" --min-train-tasks 1000 --min-validation-tasks 100
uv run w8-biayn data cache upload --path .w8-biayn/data/skyrl-full --gcs-prefix "gs://<project>-w8-biayn/datasets/cpp-perf/cpp-perf-v1/full-official/${RUN_ID}/skyrl" --credentials .gcp-service-account.json
```

Admission gates:

- train tasks >= 1000;
- validation/test tasks >= 100;
- coverage >= 95 percent line and 85 percent branch;
- visible and hidden tests exist;
- reference performance exists.

Generated local data belongs under `.w8-biayn/` and is ignored by git.

## PIE Task Rules

- `v0` slower code becomes the prompt.
- `v1` fast code is not shown during GRPO.
- `v1` may be used as SFT target, coverage/reference input, and oracle
  material.
- Train/validation/test split stays by problem.
- A task requires visible tests, hidden tests, reference performance, and at
  least 95 percent line / 85 percent branch coverage.

The prompt may include visible tests and `v0`. It must not include hidden tests
or `v1`.

## Reward Rules

Model outputs must contain exactly one `<reasoning>...</reasoning>` block
followed by exactly one fenced C++ code block. The code may start on the next
line or after whitespace on the opening C++ fence line; any second code block is
invalid.

The reward is correctness gated:

- invalid format: negative;
- recoverable C++ with missing wrapper/fence format: shaped below the
  correctness-only fallback;
- compile or sanitizer failure: negative;
- timeout: negative;
- partial tests: below any fully correct answer;
- fully correct with missing non-timeout runtime measurement:
  correctness-only fallback below any measured fully correct answer;
- fully correct: base reward plus bounded runtime-efficiency;
- child-process CPU time in nanoseconds: RL reward metric;
- wall-clock nanoseconds: diagnostic metric.

The sandbox compiles candidate and PIE `v1` oracle, runs visible and hidden
tests, then benchmarks both binaries in the same Docker sandbox with the same
CPU pinning, compiler flags, and tests. Do not add PMU, Linux perf, PERFMON, or
`perf_event_paranoid` dependencies.

## SLIME Training Workflow

Start inside the generated SLIME container:

```bash
uv run w8-biayn slime setup
.w8-biayn/slime/run-container.sh
```

Use the generated launcher rather than ad hoc `docker run` commands. It mounts
the repo, `/var/run/docker.sock`, the host Docker CLI, model cache, and a
short host-visible temp root (`SLIME_HOST_TMPDIR`, default `/tmp/w8-biayn-slime-${USER:-user}`) that is
exported as `TMPDIR` and `RAY_TMPDIR` inside the container so nested Docker
reward bind mounts and Ray sockets both work.

Moonlight C++ lane:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_data.sh
bash examples/slime/moonlight_cpp_perf/eval_base.sh
bash examples/slime/moonlight_cpp_perf/sft.sh
bash examples/slime/moonlight_cpp_perf/eval_sft.sh
bash examples/slime/moonlight_cpp_perf/grpo.sh
bash examples/slime/moonlight_cpp_perf/eval_grpo.sh
bash examples/slime/moonlight_cpp_perf/compare.sh
```

The historical dataset-release pipeline is specified in
`docs/PRIMARY_SFT_DATASET_GENERATION_PIPELINE.md`; it is separate from local
task-family remediation. It is implemented in
`src/w8_biayn/aider_sft/` and exposed through the repo-owned
`w8-biayn data aider-sft ...` CLI, including plan/inventory, reviewed build and
finalize, producer verification, sanitized export, and consumer verification.
The pilot profile remains draft. The source-only profile records a frozen,
operator-bound runtime identity and promoted inventory, but local identity,
admission gates still fail closed; human review is an optional audit. The source-only profile has
completed a verified local 75-row release, whose generated bytes remain ignored
by Git; no ready 96-root pilot is claimed. The pilot target is 96 admitted roots (72
train, 12 validation, and 12 internal test), starting from exactly 75
frozen non-benchmark Exercism candidates and admitting at least 21
human-approved LLM-assisted roots, with LLM backfill for source
rejections/category deferrals and zero overlap with the 26 official Aider C++
roots.

Use `aider-sft-source-only-75-v1` when the requested dataset is exactly the 75
source roots in train with zero validation/test and no LLM authoring. That
profile rejects `[llm]` configuration and paid-call acknowledgement, provides
no backfill for a rejected or failed source, and remains subject to the same
oracle, sanitizer, contamination, token/mask, final split/release approval,
and producer/consumer verification gates. It is distinct from the 96-root
pilot.

Use the repo-owned `prepare-tokenizer` and `prepare-seccomp` commands for the
pinned runtime assets. The tokenizer snapshot is tokenizer-only and binds
`transformers==4.57.6`, `jinja2==3.1.6`, and
`fix_mistral_regex=true`; it must not contain model weights. `plan` reads the
compiler path, full version, and binary digest inside
the exact locked grader image, never from the host compiler. Clone and preserve
the exact clean pinned SLIME checkout as well. Finalization loads its mask
utility from `SLIME_ROOT` or `.cache/upstreams/slime` without needing SLIME on
`PYTHONPATH`, and initializes it before entering any task-scoped final gate.

Complete mechanical source admission/classification before any paid LLM call,
derive the exact missing total/category/split cells, and require candidate
capacity of at least three times required LLM admissions. Do not carry forward
the obsolete fixed candidate cap.

For this pipeline, preserve the source grader's C++17 dialect. Compile the
exercise target separately, discover/run Catch without CTest/default-`ALL`
ambiguity, and run a fresh locked sanitizer build. Normal and sanitizer
configure must pass the explicit `Unix Makefiles` generator and locked compiler
inside the enforced fingerprinted sandbox; sanitizer admission has its own
positive discovery and must match the normal count. Reuse repeated Catch files
through one content-addressed support bundle. Convert Docker `fsize` from MiB
to bytes, and accept pinned Catch v1 discovery status only when zero or equal
to the parsed positive count. Source resume reuses terminal records only under
the current admission fingerprint; stale mechanical failures and historical
late rejections caused by run-level preflight errors rerun, and an empty pool
returns structured `source_only_shortfall`. LLM tasks use the repo-owned
C++17 CMake/Catch scaffold and cannot emit build commands. Contamination is
role-aware: allowlisted support/scaffold matches are excluded, semantic task
matches are not. The final rendered ID scan matches whole slugs, not
hyphen-delimited substrings of valid compound source IDs. Keep the prompt
contract compact enough for every frozen source-only row to fit the locked
4096-token sequence without truncation.

V1 is autonomous once mechanical stages pass. Source inventory, LLM usage
terms, LLM admission, contamination near-matches, the final split, and the
rendered release package may be exported for scope-specific fingerprint-bound
human audit. Keep candidate states separate from dataset
split/release. A late task-scoped rendered-row/token/contamination failure
invalidates the split and returns to quota-preserving backfill before
`dataset_release`. Run-level profile/consumer preflight failures leave admitted
candidates and the frozen split intact. Bind renderer and final-screen policy
fingerprints into late rejection journals so `--resume` retries preserved
evidence after a policy correction. Mutable
state and locks live in the sibling `.state/` directory; the ready root is
immutable. Readiness uses mandatory schema-v2 bindings for the token ledger and
release-review subject.

Rows reach SLIME as final-answer-only raw message lists. The thin repo adapter
forwards exact template kwargs with thinking disabled and applies explicit qwen
assistant loss; dataset-loader `--apply-chat-template` is forbidden. Export the
private-asset-free internal bundle with recomputable token/mask records. The
producer runs full `verify`; the lane runs `verify-export` using only sanitized
bytes, pins exact model/tokenizer/template/adapter identities, rejects token/
mask/sequence drift, and disables auto-prepare. Readiness requires no
target-model responses, repair rows, training, benchmarking, or uplift. Treat
the current one-row helpers below as seed fixtures, not the primary pipeline.

When a trusted internal recipient explicitly wants only the established
Moonlight Aider-task row shape, use `w8-biayn data aider-sft export-minimal`.
It verifies the ready source, never changes that immutable root, and writes a
sibling directory containing exactly one `train.jsonl`. The projection keeps
only `label`, role/content messages, six compact metadata fields, and
`task_id`, while preserving message content exactly. It is not the full
provenance-bearing `slime-sft` consumer bundle.

Optional Moonlight single-sample Aider `whole` format SFT smoke. This is a
compact Aider-like task-text-plus-starter-files check only, not PIE training
evidence. Build the one-row data with:

```bash
uv run python -m w8_biayn.integrations.moonlight_single_sample_sft \
  --out .w8-biayn/data/aider-whole-single
```

To convert the local Leap task folder itself into one-row SFT data, first create
the task and then build the SFT JSONL from its `.docs`, starter files, and
`.meta/example.*` reference files:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_leap_aider_task.sh --force
bash examples/slime/moonlight_cpp_perf/prepare_leap_aider_sft_data.sh --force
```

This writes `.w8-biayn/data/aider-leap-sft`; point `SLIME_CPP_DATA_DIR` there
for the SFT stage when training on the task-folder version.

For an explicitly requested all-task local SFT projection, use the dedicated
`aider-tasks-sft-dataset` skill and the repo-owned
`w8-biayn data aider-tasks-sft build|verify` CLI. The converter matches the
existing `.w8-biayn/data/aider-tasks-sft/sft/train.jsonl` shape, excludes all
`.state` controls, qualifies colliding task IDs, and writes
`.w8-biayn/data/aider-tasks-reverify-sft`. Do not describe that projection as
primary-pipeline readiness, token/mask evidence, a release, or training proof.

Then run the existing non-LoRA `examples/slime/moonlight_cpp_perf/sft.sh` with
`SLIME_CPP_DATA_DIR` pointed at that directory and
`SLIME_CPP_AUTO_PREPARE_DATA=0`. Do not run `prepare_data.sh`, GRPO, GLM, or
the LoRA lane for this smoke.


For response-only inspection with no training, first create the local Leap task
with `examples/slime/moonlight_cpp_perf/prepare_leap_aider_task.sh --force`,
then use `examples/slime/moonlight_cpp_perf/probe_and_grade_aider_task.sh`
against an already running OpenAI-compatible model server and that task
directory. It builds the Aider-like prompt from `.docs` plus editable starter
files, saves `response.txt`, applies returned whole-file blocks to a clean copy,
runs CMake, and writes `grade/summary.json` plus configure/build logs.


Optional Moonlight Polyglot C++ base-eval benchmark. This is not active PIE
training and not an official Aider leaderboard run; it is a repo-owned
SLIME rollout-only eval of base Moonlight on C++ Exercism tasks. Keep detailed
setup, response contract, artifact fields, category summaries, blocking
`files.example` same-grader oracle preflight, schema-v2 incremental oracle
records, task/grader/image fingerprints, strict on-disk reconciliation, and
`recovered_*` diagnostics in `examples/slime/moonlight_polyglot_cpp/README.md`
instead of duplicating them
across repo-wide docs:

Keep `--rollout-skip-special-tokens` enabled in the launcher. Terminal
tokenizer markers such as `<|im_end|>` are a decoding concern; do not weaken
the strict whole-file parser to accept them as response content.

Use `w8_biayn.integrations.slime_polyglot_cpp compare-runs` for historical
pass@k visualization. Require exactly two successful, oracle-clean runs with
uniform samples per task, identical task and immutable oracle-fingerprint sets,
and matching model/sampling/grader receipt fields. The report uses six
mutually-exclusive medium-grained presentation categories for grouped pass@k
bars, stacked outcomes, and a compact dot/range view; it does not replace the
stored fine-grained multi-label category summary. Include the admitted
`files.example` answer in every overall and category view as a 100%-passing
same-grader setup reference, never as a generated model series or official
Aider score. Keep task-level empirical pass@k distinct from model-sample outcome
rates and oracle setup-preflight outcomes, and keep recovered-format results
diagnostic only.

For intentional historical sampling differences, allow only the explicit
`--allow-config-mismatch eval_temperature` and/or `eval_top_p` override.
Persist the mismatched per-run values, switch the report to descriptive mode,
put sampling settings in series labels, and warn that differences cannot be
attributed to `k` alone. Model, task, oracle fingerprint, grader, response,
and timeout mismatches stay blocking.

The optional `gemini-sanity` command is limited to one admitted Polyglot task
and must reuse the exact saved prompt, raw API response, strict parser, and
Docker grader. Dry-run before spending; take `GOOGLE_API_KEY` or
`GEMINI_API_KEY` from the environment without persisting its value; pin an
exact model id; expose no oracle/tests; and label the result a cross-model
sanity check rather than pass@k or an official Aider comparison. Recovery is
diagnostic only. Preflight a host-writable artifact path before spending the
paid API request.

```bash
bash examples/slime/moonlight_polyglot_cpp/prepare_data.sh
bash examples/slime/moonlight_polyglot_cpp/eval_base.sh
```

Optional official Aider/Modal C++ base evaluation. This is not active PIE
training, not a SLIME lane, and not the repo-owned Moonlight Polyglot harness.
It runs base `zai-org/GLM-4.7-Flash` through Aider's exact edit/test/retry
benchmark on an ephemeral Modal App. The only entrypoint is export-only
`examples/modal/glm47_flash_aider_polyglot_cpp/run.sh`; plan is the default
and no-spend, while smoke/full require explicit acknowledgement and full always
runs the real two-task smoke first.

Keep Modal tokens local, optional `HF_TOKEN` downloader-only, and the random
SGLang bearer limited to the server and Aider runner. Pin exact model, Aider,
Polyglot, SGLang-image, Modal-SDK, settings, and strict `H100!:4` identities.
Use separate model/results Volumes, one server replica, `min_containers=0`,
bounded timeouts, explicit stop plus control-plane verification, and ignored
local artifacts. Preserve official Aider rows/histories/stats; `pass_rate_2`
is sequential second-try success, never pass@2. Source/offline completion is
not live evidence: do not report a model result before the two-task smoke and
complete 26-task stopped-App receipt.
Allow a 3600-second cold-start ceiling, poll the SGLang child process for early
exit, and persist/print only a bearer-redacted `server.failure.json` tail on
startup failure; raw SGLang output stays ephemeral.
Overlay the SGLang base with official Transformers commit
`76732b4e7120808ff989edbd16401f61fa6a0afa`, fail image construction unless
`glm4_moe_lite` is registered, and persist that identity in plans and
receipts.
Run stale-result admission on CPU before model loading or GPU startup. A
server restart may accept only the active run's identity-compatible config;
do not let the server freshness guard reject artifacts written by its own
benchmark runner.
Use up to 2048 configured completion tokens for the authenticated chat probe;
128 tokens can be consumed entirely by GLM reasoning. Admission diagnostics
may store only response keys, presence flags, lengths, finish reason, and
numeric usage, never generated reasoning or answer text.
Keep the Aider checkout at `/aider`, matching its absolute official C++ grader
path `/aider/benchmark/cpp-test.sh`, and build-check that executable contract.
On exception-only rows, print and persist only bearer-redacted task names,
exception types, and final traceback lines in `exception.summary.json`.
Set the Aider completion budget to 32768: a paid smoke showed that GLM can
spend all 8192 tokens reasoning without editable content, while the pinned
checkpoint has a 202752-position context. Admission-failure output may include
only safe per-task counters; download committed failure artifacts locally
before re-raising the remote exception.
Pinned Modal SDK 1.5.2's `App.server` path silently inherits the underlying
Function's 300-second execution timeout. Do not use it for this long-lived
SGLang endpoint: it recycles the four-H100 container approximately every five
minutes. Use `@app.function` plus `@modal.web_server` and set the explicit
execution timeout to startup timeout plus the complete runner timeout plus 600
seconds. Persist the derived value in plans and receipts. Keep static
`min_containers=0`, then dynamically hold exactly one replica with
`min_containers=1` after CPU/Volume admission and model-cache preparation.
Keep that active lease through all Aider work. On success or error, restore
`min_containers=0` with a two-second drain before transfer; explicit stop plus
control-plane verification remains mandatory. The 1200-second scaledown window
is an identity-bound fallback. The explicit lifetime and active lease are
operational, so compatible earlier artifacts may resume without an identity
mismatch.
Modal SDK 1.5.2 Volume entries expose an `IntEnum`; never classify them through
`str(entry.type)`. Download only `FileEntryType.FILE`, skip every non-regular
entry, and retain strict byte reconciliation. Validate the full entry list
before writing locally, then download with the SDK async API at a fixed
16-file concurrency bound. After the committed benchmark result returns,
lower the server scaledown window to two seconds before transfer so the H100s
do not remain allocated for artifact copying.


```bash
bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh
```

The updated independent design uses exactly eight isolated trajectories per
task and up to two sequential Aider tries per trajectory. Report only
`pass@1_try1`, `pass@1_try2`, `pass@8_try1`, and `pass@8_try2`; try-2 success
is cumulative and may use feedback only from the same trajectory's try 1.
Require separate try-depth matrices, the frozen seed schedule, the extra paid
acknowledgement, a 2-by-8-by-try smoke, complete artifacts, and stopped-App
proof. Source and offline tests implement this contract; paid seed inspection,
the sampling smoke, and the complete stopped-App full receipt remain mandatory.
Paid acknowledgements are launch safety gates rather than immutable benchmark
identity and may change from false in plan mode to true for the first paid run.
Pin every sampling-smoke trajectory to `binary-search-tree` and `grade-school`
with Aider's comma-separated keyword filter. Store corrected evidence under
`sampling-smoke-v1`; preserve randomized legacy smoke artifacts as diagnostics
but never reuse them on resume.
Independent full requires `W8_MODAL_AIDER_MAX_RUN_SECONDS=14400`; a prior
7200-second run must get a fresh ID because timeout remains immutable identity.
Aider's `num_exhausted_context_windows` field counts provider
`finish_reason=length` output-limit events. Keep it diagnostic; never reject
otherwise complete non-exception rows with C++ test invocations solely because
that counter is nonzero.
Persist `runner.identity.json` before benchmark work and bind non-resume worker
re-entry to the same Modal App plus immutable config. Explicit independent
resume reuses only validated complete sample rows with stats, archives an
interrupted sample under `incomplete-attempts/`, and restarts only that sample
from the pinned tree and seed. Preserve the prior local failure download under
`resume-download-archives/` before exact resumed transfer. The active-server
lease is compatible with pre-lease artifacts. Generate offline visual reports
with `python -m w8_biayn.modal_aider_visualization`; it reads only local
evidence, supports explicit partial-prefix diagnostics, and writes under
`reports/<run-id>/` instead of the canonical run tree. Keep its stable
six-group topic taxonomy (3-6 tasks per group) and balanced 8/9/9
Easy/Medium/Hard task-complexity taxonomy distinct from model-derived outcome
rates.

Optional Moonlight Multi-SWE C++ base-eval benchmark. This is not active PIE
training and not an official Multi-SWE leaderboard run; it is a repo-owned
SLIME rollout-only eval of base Moonlight on C++ issue-resolution tasks from
`ByteDance-Seed/Multi-SWE-bench_mini`. Preparation is a blocking admission
gate: select the official lowercase per-instance `mswebench` image, pin its
immutable identity, and grade in its exact prepared checkout/build/test assets
without per-task GitHub clones. Run every dataset `fix_patch`, require a
positive CTest count, persist after each task, and reuse only
fingerprint-matching passing records on resume. The proof lives in `data/oracle.records.jsonl`,
`data/oracle.summary.json`, `data/sandbox-images.json`, and the schema-v3
manifest; aggregation copies it into `eval/base.oracle.records.jsonl` plus
`oracle_setup_check` in `eval/base.summary.json`. Keep detailed setup, response
contract, artifact fields, repo summaries, oracle proof, and `recovered_*`
diagnostics in `examples/slime/moonlight_multi_swe_cpp/README.md` instead of
duplicating them across repo-wide docs. For simdjson PRs 958, 1615, 1712, and
2016, preparation must populate the checksum-pinned data-local
`cxxopts`/simdjson-data cache and the grader must mount it read-only while
retaining `--network none`. PR 958 must propagate only
`-Wno-error=effc++` from the external cxxopts target after simdjson's
target-level `-Werror`, use an external-header wrapper that keeps the full
`-Weffc++` group visible but non-fatal, and remove only the network-dependent
checkperf include; do not disable
warnings-as-errors or the ordinary benchmark/test build globally. Nlohmann PR
2099 must run the dataset's other 49 CTests plus the PR-relevant `CBOR` and
`MessagePack` doctest cases explicitly, excluding only their unrelated
historical roundtrip fixture cases:

Keep `--rollout-skip-special-tokens` enabled in the launcher. Terminal
tokenizer markers such as `<|im_end|>` are a decoding concern; do not weaken
the strict single-diff parser to accept them as response content.

```bash
bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh
bash examples/slime/moonlight_multi_swe_cpp/eval_base.sh
```

Moonlight rank-16 LoRA C++ lane:

```bash
bash examples/slime/moonlight_lora_cpp_perf/prepare_data.sh
bash examples/slime/moonlight_lora_cpp_perf/eval_base.sh
bash examples/slime/moonlight_lora_cpp_perf/sft.sh
bash examples/slime/moonlight_lora_cpp_perf/eval_sft.sh
bash examples/slime/moonlight_lora_cpp_perf/grpo.sh
bash examples/slime/moonlight_lora_cpp_perf/eval_grpo.sh
bash examples/slime/moonlight_lora_cpp_perf/compare.sh
```

The LoRA lane resolves rank-16 LoRA flags from the active SLIME/Megatron help
surface and fails before training if the runtime does not advertise a supported
LoRA rank flag.

GLM C++ lane when present:

```bash
bash examples/slime/glm47_cpp_perf/prepare_data.sh
bash examples/slime/glm47_cpp_perf/eval_base.sh
bash examples/slime/glm47_cpp_perf/sft.sh
bash examples/slime/glm47_cpp_perf/eval_sft.sh
bash examples/slime/glm47_cpp_perf/grpo.sh
bash examples/slime/glm47_cpp_perf/eval_grpo.sh
bash examples/slime/glm47_cpp_perf/compare.sh
```

GLM agentic SWE-agent file-state lane. SWE-agent (not claude-code) edits
`candidate.cpp`; the final FILE is graded in the repo's Docker sandbox (not E2B)
and the correctness-gated reward flows via the OpenAI adapter `finish_session`.
The `generate` hook is `w8_biayn.integrations.slime_swe_agent_cpp_perf.generate`;
the driver is `swe_agent_driver.py`; the grader seam is
`w8_biayn.cpp_perf.sandbox.run_in_directory_prewritten`. SFT stays single-turn;
base/sft/grpo evals and GRPO are agentic. SWE-agent runs its edit/bash loop
in-process on the rollout worker via swerex `LocalDeployment` (`{"type":
"local"}`) — there is no sibling execution container and no `--network host`
(which collided with Ray's `127.0.0.1` node-ip), and each concurrent rollout
copies the repo to a unique basename so drivers do not share one working tree.
Only final-file grading re-enters the hardened `w8-biayn-cpp-perf` Docker image;
the `swe-image` CLI/dockerfile stays for reference but is off the hot path.

```bash
bash examples/slime/glm47_swe_agent_cpp_perf/prepare_data.sh
bash examples/slime/glm47_swe_agent_cpp_perf/eval_base.sh
bash examples/slime/glm47_swe_agent_cpp_perf/sft.sh
bash examples/slime/glm47_swe_agent_cpp_perf/eval_sft.sh
bash examples/slime/glm47_swe_agent_cpp_perf/grpo.sh
bash examples/slime/glm47_swe_agent_cpp_perf/eval_grpo.sh
bash examples/slime/glm47_swe_agent_cpp_perf/compare.sh
```

Status: **proven end-to-end** (run `w8swe-20260707091714`, 78 min, all seven
stages incl. a clean GRPO weight update: finite kl, zero-variance-fraction 0,
trained_tokens_mean 161, 87.5% eval pass everywhere, checkpoints + HF exports
persisted to GCS). Every campaign incident is pinned by a regression lint in
`tests/test_regression_lints.py` — if one fires, read its docstring before
"fixing" the assert. Open before a full run: episodes still fork 3-ways in
the adapter (keep-best guard preserves GRPO group shape but discards ~2/3 of
captured tokens; investigate REALIGN vs GLM think-stripping), plus thinking
budget, PIE admission coverage, and the model/torch_dist GCS cache.

Hard-won invariants for this lane (each one cost a paid smoke; keep them):

- **swerex LocalDeployment shares one filesystem across episodes AND stages.**
  Its `upload` is bare `shutil.copytree` (no `dirs_exist_ok`); SWE-agent
  uploads tool bundles to the fixed `/root/tools/{bundle}`. The driver
  monkeypatches `LocalRuntime.upload` to be idempotent
  (`_patch_swerex_local_upload`, a vendored-surface shim — re-check on swe-rex
  pin bumps), uses a unique repo basename per attempt, and rmtrees the root-FS
  copy afterward. Also note `/root/state.json` is shared by concurrent
  episodes (tool-state bleed; accepted for now).
- **HF-export gates require real weight shards** (`hf_export_ready`), restores
  prune weightless exports, and the GCS persist is loud with one retry — an
  index-without-shards restore once hung SGLang ~85 min.
- **Every trainer-reaching sample needs `metadata.round_number`** (slime's
  `--log-multi-turn` KeyErrors otherwise); abort husks reach the trainer, so
  `_abort_result` stamps it too, plus `abort_reason`/`abort_error` (exception
  message — never strip it to just the type name).
- Group size `--grpo-n-samples-per-prompt` (default 8; 1 zeroes every
  group-relative advantage, `kl=nan`); global batch derives as
  rollout_batch × n_samples. The sid rides in the request body via SWE-agent's
  `completion_kwargs` (`user` + `extra_body.metadata.session_id`) besides the
  bearer.
- **Exactly one trainable sample per episode**: slime reshapes rewards as
  (prompts × n_samples) and `--log-passrate` asserts on it; the hook keeps the
  fork with the most trained tokens and reports drops as
  `rollout_health/fork_samples_dropped_mean`.
- **Network failures bubble up**: launches preflight reachability before
  spending (hard-fail on dead googleapis), a watchdog emits
  `net_degraded`/`net_recovered` launch events throughout, and a vanished spot
  cluster returns `CLUSTER_LOST` into the provisioning retry loop instead of
  being ghost-polled. Manual probe: `w8-biayn ops net-check`
  (`src/w8_biayn/net_health.py`). Pinned upstream fetches skip the network
  when the commit is already local.

W&B is the primary observability surface (module `src/w8_biayn/wandb_report.py`;
one launch = one group = run id; per-stage runs `<run-id>-<stage>` with
deterministic ids via `WANDB_RUN_ID` + a train-entry rename shim because pinned
slime ignores `--wandb-run-id`). Where data goes: SLIME `train/*`/`rollout/*`
natively; live `rollout_health/*` (abort reasons, zero-variance group fraction,
correctness-gate rates, agent steps) from the generate hook via shared mode;
`eval/*` + per-task tables + `eval/abort/<reason>` from the offline scorer onto
the stage's own run (same keys overlay base/sft/grpo); uplift table + summary
and launch outcome/config/checkpoint-reference-artifact on `<run-id>-pipeline`;
`pipeline/elapsed_seconds` + a timeline table for milestones (never raw unix
scalars); `wandb.alert` on all-abort evals, >30% abort rate, and failed
launches. Push the curated saved view with
`uv run --extra cloud w8-biayn wandb workspace` (wandb + wandb-workspaces live
in the cloud extra).

For a GPU box you SSH into yourself (no GCP/SkyPilot/Google keys), follow the
README "SSH Manual Run" section: host setup + local PIE build, then
`.w8-biayn/slime/run-container.sh` and the lane stages with `SLIME_*` env
knobs; only `WANDB_KEY` from `.env` is needed, and checkpoints stay local.

Use local receipts (`run.log`, `run_receipt.txt`, `vram_usage.csv`,
`vram_peak.txt`), debug rollout dumps, W&B links when configured, and eval
summaries for evidence. The paid GCP GLM full launch is
`uv run --extra cloud w8-biayn launch glm47-full` (dry-run first with
`--dry-run`; implementation `src/w8_biayn/cloud_launch.py`, with the old
`examples/slime/glm47_cpp_perf/launch_gcp_h100_full.py` kept as a thin shim).
Keep it a provisioning wrapper around the repo-owned GLM SLIME lane, with
dry-run rendering, scoped secrets, downloaded local artifacts, labels, spot
support via `--use-spot`, and automatic teardown. The W&B key resolves from
`--wandb-api-key-file`, `WANDB_API_KEY`, or a `WANDB_KEY` entry in `.env`
(`.env.sample` documents the only key read from `.env`).

The launch restores `tasks-full` from a project-scoped, gate-keyed GCS cache
(`gs://<project>-w8-biayn/cache/<version>/tasks-full/mintrain..-minval..-mintest..`)
before building, builds only on a miss, and repopulates the cache after — so
the PIE build runs once per (cache version, admission gates) and is shared
across users. It provisions a 1024GB boot disk by default (`--disk-size`): the
30B model is staged ~4x (HF download, torch_dist conversion, SFT checkpoint,
HF export) and 256GB overflows mid-export. Each launch also writes a
`<run-id>-pipeline` W&B run with timestamped preamble milestones.

Checkpoints are ephemeral unless persisted: on exit the launch rsyncs the run's
Megatron checkpoints and HF exports to `gs://<project>-w8-biayn/runs/glm47/<run-id>/`
(even for a partially-completed run), and `--resume-from-run <old-id>` restores
them into a new run and sets `SLIME_RESUME_SKIP_COMPLETED=1` so the lane skips
training stages whose Megatron checkpoint and HF export already exist
(`stage_already_complete` in `glm47_cpp_perf.sh`). Never assume a torn-down run
is resumable unless its checkpoints reached GCS — the launch teardown or
`ops down-run` deletes the node's disk.

## Tool Interlinkage

`w8-biayn` is the single management CLI. It wraps deeper tools; when a cloud
or training behavior looks wrong at the CLI level, drop down to the wrapped
tool and its documentation:

- Cloud hardware: `w8-biayn launch glm47-full` and `w8-biayn ops
  status|logs|down|queue` wrap SkyPilot, pinned in
  `w8_biayn.constants.SKYPILOT_PIN` and installed through the `cloud` extra
  (`uv run --extra cloud ...`). Debug directly with `uv run --extra cloud sky
  status|logs|down` and https://docs.skypilot.co. Semantics that matter:
  `sky.launch` on API-server builds resolves at job submission, so the CLI
  tracks the job to a terminal state before declaring success; the client
  version must match any locally running sky API server.
- Teardown safety (three layers): (1) the launch downloads artifacts and downs
  the cluster on any exit — but a killed/hung launch process cannot run its
  `finally` block; (2) so the launch arms SkyPilot `idle_minutes_to_autostop`
  (default 20, `--idle-autostop-minutes`, `0` disables) with `down=True`, and
  the on-cluster autostop *terminates* the cluster once the job ends and it
  idles, independent of the launcher process (this closes the gap that once
  orphaned a paid A100 for ~6 hours when a background launcher was SIGKILLed
  mid-teardown); (3) as a last resort every instance is tagged
  `labels.run_id=<run>` (the W&B group id) so
  `w8-biayn ops down-run <run-id> --execute` is the launcher-independent reaper
  that downs the cluster by name and deletes any GCE instance still carrying the
  label. After any launch, confirm no orphan with
  `gcloud compute instances list --filter=labels.project=w8-biayn`.
- Training: lane scripts wrap SLIME (pinned checkout at
  `.cache/upstreams/slime`, docs under `.cache/upstreams/slime/docs`).
  Megatron model args come from `scripts/models/*.sh` inside that checkout;
  the SLIME train loop is vendored in
  `src/w8_biayn/integrations/slime_train_entry.py` and must be re-diffed on
  pin bumps. The GLM container run also fetches/checks out `SLIME_PIN` (no
  drift to HEAD) and applies an in-place Megatron dist-checkpoint patch (in
  `cloud_launch.build_container_script`) so converted checkpoints load: TE
  `_extra_state` objects that HF conversion writes in a format the trainer
  cannot read are nulled, and `slime_train_entry` disables
  `ckpt_fully_parallel_load`. Re-verify both on a SLIME/Megatron/TE bump.
- GLM lane on non-Hopper GPUs: the default `alltoall` MoE dispatcher and
  `EP=4` (ETP*EP*PP must divide the 8-GPU world) are required on A100; DeepEP
  `flex` and `EP=8` are Hopper/16-rank only. GLM-4.7-Flash is a thinking model,
  so response budgets are 2048 and seq-length 4096 (512 truncated 100% of
  generations). These live in `examples/slime/glm47_cpp_perf/glm47_cpp_perf.sh`
  with `SLIME_GLM_*`/`SLIME_*` env overrides.
- GCP accounting and quotas: use `gcloud compute instances list` and the Cloud
  Quotas API with the scoped service-account env (never `gcloud auth
  activate-service-account`). Newer GPU quota limits (H100 class) are visible
  only through the Cloud Quotas API, and on-demand H100 is not self-service —
  spot/preemptible quota is.

## Git And Artifact Hygiene

Do not delete user files unless explicitly asked. If a generated artifact is
tracked but should not be in git, use `git rm --cached` so the working-tree file
remains available.

Never commit `.env`, `.gcp-service-account.json`, `.w8-biayn/`,
`.cache/upstreams/`, PIE data, CodeNet data, SuperCoder data, gem5 outputs,
logs, rendered configs, checkpoints, model exports, generated `RUN_REPORT*`
files, or generated report asset directories.

## Documentation Rules

When commands, setup, dataset shape, cache behavior, task schema, reward logic,
launch flow, benchmark protocol, or supported active pipelines change, update:

1. `README.md`
2. `ROADMAP.md`
3. `.agents/REPO_GUIDE.md`
4. this skill
5. `docs/AIDER_SFT_SCOPE.md` and `.agents/skills/aider-task-family-remediation/SKILL.md`
   when local task-family workflow changes; update the historical pipeline
   document only when an explicitly authorized release contract is affected
6. tests when command behavior changes

## Validation

Before handing off:

```bash
uv run --extra dev pytest
uv run --extra dev ruff check src tests scripts
uv run python -m compileall src tests
python3 .agents/skills/agent-skills-framework/scripts/validate_skill.py .agents/skills/w8-biayn-framework
```

For setup or CLI-surface changes:

```bash
./scripts/bootstrap.sh --no-sky
uv run w8-biayn --help
uv run w8-biayn data doctor
uv run w8-biayn slime doctor
uv run w8-biayn slime setup --force
uv run w8-biayn cpp harness preflight --dry-run
```


## GLM Multi-SWE C++ Modal Evaluation

Use examples/modal/glm47_flash_multi_swe_cpp/run.sh for the optional
GLM-4.7-Flash single-turn Multi-SWE C++ Modal lane. It defaults to a redacted
no-spend plan and is not SLIME, PIE training, or an official leaderboard run.

Preserve these invariants: exact dataset revision and reviewed 50-image
linux/amd64 digest lock; all-task fix_patch Modal-Sandbox oracle before model
load; one strict H100!:4 SGLang replica with separated reasoning/content; only
message.content reaches the existing parser; fresh network-blocked,
secret-free 2-CPU/2048-MiB Sandboxes; read-only simdjson subpath mounts only;
generation completes before full grading; every Sandbox terminates/detaches;
regular-file-only bounded artifact download; explicit App stop and
control-plane verification before any score.

Under Modal SDK 1.5.2, stage the affected simdjson dependency trees beneath one
checksum-pinned parent and mount that one data-Volume subpath read-only at a
fresh /mnt path; the SDK rejects both mounting the same Volume object at
multiple Sandbox paths and mounting over the official image's non-empty
dependency directory. After patch preflight, trusted shell setup may replace
only the expected cxxopts and simdjson-data locations with symlinks into the
detached mount. Bind the setup script and layout version into the oracle cache
key. Permit source commit/file-hash migration only for incomplete oracle-only
runs with no model/server artifacts, persist the migration receipt, and reuse
passing oracle records only by exact cache key. All later resume identity stays
strict. Parse CTest discovery from complete in-memory stdout/stderr before
truncation, persist the numeric count and per-stream hashes/sizes, and retain
bounded tails from both streams. Large compiler-warning stderr must not hide
positive stdout test evidence; bind the PR 958 capture strategy into its cache
key.
Keep min_containers=0 and poll the externally routed health endpoint through
Modal Server's zero-to-one HTTP 503 window before models/chat admission. Use
bounded stage timeouts and the checked-in transient status set. Failure
diagnostics may retain endpoint/status/count/body-size/hash/truncation/JSON
keys, never HTTP body text. Permit source-only migration through preparation
and admission failures with exact oracle/model identities; block it after
successful admission or any benchmark-stage artifact.
Keep the dataset image lock out of the GPU server image. Modal Server module
hydration must accept its absence, but local orchestration must require the
reviewed lock before preflight, dataset/oracle, or paid work.
For a fresh full run, `W8_MODAL_MULTI_SWE_ORACLE_SOURCE_RUN_ID` may import the
completed smoke's all-50 proof. Validate the source locally before auth and
again in the results Volume: reconciled artifact manifest, stopped-App receipt,
exact lock/task set, admitted summary/JSONL/records, then all 50 recomputed
current oracle cache keys. Persist import lineage, import no model responses,
and fail closed without executing oracles on any mismatch.

The source/no-spend/offline-test path and fixed paid smoke are complete, while
full paid validation is pending. Require a complete stopped-App receipt before
reporting a model result.

## Agentic GLM Multi-SWE C++ Modal Evaluation

Use examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh for the optional
SWE-agent successor to the single-turn GLM Multi-SWE lane. It is export-only,
defaults to no-spend plan, and has distinct benchmark/result identities. Keep
run IDs to 3-40 lowercase letters, digits, or hyphens; this admits the
documented timestamp forms and keeps the derived Modal App name at most 62
characters.

Preserve the exact SWE-agent commit and dependency lock, one deterministic
trajectory per task, the 40-call and fixed token/time budgets, and both paid
gates for full. Before model loading or GPU startup, require the reviewed
50-image lock plus all 50 exact fix-patch oracle proofs and all 50 exact
sanitized-workspace proofs. Oracle import may come from the completed
single-turn family; workspace import must come from a completed agentic run.
Both fail closed on any cache-key mismatch and import no model response.

The model-controlled Agent Sandbox must be the exact official task image with
blocked network, no Secrets, no Volumes, and unprivileged w8agent execution.
Trusted root code owns the base snapshot and canaries, removes original
history/hidden assets, preserves and receipt-binds exact empty directories for
uninitialized gitlinks, requires populated submodules to match their indexed
commits, rewrites only required upstream root-state tool paths, tracks one
logical cwd without a persistent privileged shell, and bounds every
command and stream. Persist hashes, lengths, actions, bounded observations, and
numeric usage; never persist private reasoning or the raw SWE-agent trajectory.
Use the exact image's default C++ mode for the workspace compile/output canary
because reviewed legacy images may reject C++20 flags; this must not change task
grader commands.

After stopping the agent, reject symlinks, hardlinks, special files, traversal,
binary changes, forbidden paths, and oversized trees. Synthesize the final
file-state diff in trusted code and require it to apply to a second pristine
reconstruction. Agent-limit outcomes may still grade a valid final state;
infrastructure failures do not enter the denominator.

The pinned hook persists every completed step incrementally, but only through
hashed/bounded safe events and tool receipts. Hold exactly one H100!:4 server
replica only during trajectories. Full repeats the fixed smoke, lowers the
server for smoke grading, re-acquires and re-admits it, then runs all 50.
Require all selected trajectory and patch units before lowering min_containers
to zero with the two-second drain. Grade afterward in separate fresh,
network-blocked official-image Sandboxes. Resume only complete
identity-compatible units and restart an incomplete unit once from pristine
state.

Source/no-spend/offline tests are complete; paid CPU canaries, SGLang
admission, one trajectory, fixed smoke, and full evidence are pending. Do not
report a score before 50 complete trajectories and records, passing exact
oracle/workspace proofs, byte-reconciled artifacts, and stopped-App proof.
Use the lane README as the canonical runbook.
