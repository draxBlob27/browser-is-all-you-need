---
name: w8-biayn-framework
description: "Maintain, extend, test, document, and operate the w8-biayn C++ performance-RL pipeline now focused on SLIME-based Moonlight and GLM training: PIE task setup, SLIME JSONL conversion, Megatron/SGLang launch wrappers, Docker C++ rewards, local run receipts, and held-out uplift evaluation. Use for work in this repo, especially when touching SLIME, Moonlight, GLM, PIE data, C++ reward/eval, repo guidance, or legacy SkyRL/rLLM migration boundaries."
---

# w8-biayn Framework

Use this skill for work in this repository. Keep workflows reproducible from a
fresh clone and prefer repo-owned commands/wrappers over one-off shell history.

## Source Of Truth

Read these before changing behavior:

1. `AGENTS.md`
2. `README.md`
3. `ROADMAP.md`
4. Relevant code under `src/w8_biayn/`

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

Use `uv run w8-biayn upstreams clone` for pinned upstream copies under `.cache/upstreams/`. Temporary study clones may live under `/tmp`; do not vendor upstream repos or data. Experimental sidecar frameworks such as SLIME may be pinned for exploration only when explicitly requested; they must not replace the active SkyRL/rLLM C++ training path without an explicit project-phase change. When working on the SLIME sidecar lane, prefer the repo-owned `w8-biayn slime setup` Docker-first flow instead of trying to force SLIME runtime dependencies into the main project virtualenv. For an explicit SLIME C++ PIE run, build prompt JSONL with `w8-biayn data slime build` and use the separate `examples/slime/cpp_perf/` launcher and `generate_with_cpp_perf.py` reward hook. For the text-only SLIME bring-up path, prefer the repo-owned DAPO-Math prep script plus `examples/slime/multi_agent/run_multi_agent_text.sh` wrapper instead of editing the upstream example directly.

Use `uv run w8-biayn upstreams clone` for pinned upstream copies under
`.cache/upstreams/`. Temporary study clones may live under `/tmp`; do not vendor
upstream repos or data.

## Active Repository Map

- Bootstrap: `scripts/bootstrap.sh`
- CLI: `src/w8_biayn/cli.py`
- Dataset setup and manifests: `src/w8_biayn/cpp_perf/data.py`
- Coverage measurement: `src/w8_biayn/cpp_perf/coverage.py`
- PIE parsing/task construction: `src/w8_biayn/cpp_perf/pie.py`
- SkyRL dataset conversion: `src/w8_biayn/cpp_perf/skyrl_dataset.py`
- SLIME dataset conversion: `src/w8_biayn/cpp_perf/slime_dataset.py`
- Eval aggregation: `src/w8_biayn/cpp_perf/eval.py`
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

Legacy SkyRL/rLLM/GCP control-plane files include
`src/w8_biayn/cpp_perf/skyrl_dataset.py`, `src/w8_biayn/sky_config.py`,
`src/w8_biayn/run_status.py`, `src/w8_biayn/mlflow_metrics.py`,
`src/w8_biayn/grpo_readiness.py`, `src/w8_biayn/integrations/skyrl_*.py`,
`src/w8_biayn/integrations/cpp_perf_env.py`, and
`src/w8_biayn/integrations/cpp_eval_main.py`. Leave them alone unless the task
explicitly asks for legacy work.

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
Define the Server with static `min_containers=0`, then dynamically hold exactly
one replica with `min_containers=1` after CPU/Volume admission and model-cache
preparation. Keep that active lease through all Aider work. On success or
error, restore `min_containers=0` with a two-second drain before transfer;
explicit stop plus control-plane verification remains mandatory. The
1200-second scaledown window is a fallback and stays identity-bound. The active
lease is operational, so compatible artifacts created before it may resume
without an identity mismatch.
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
lease is compatible with pre-lease artifacts.

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
5. tests when command behavior changes

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

The source/no-spend/offline-test path is implemented, while paid validation is
pending. Require the paid ladder and a complete stopped-App receipt before
reporting a model result.
