# SLIME C++ Performance-RL Roadmap

This roadmap describes the current training process from first principles. The
active stack is SLIME with Megatron training and SGLang rollouts, focused on
Moonlight and GLM models.

The project trains a model to rewrite C++ programs:

```text
correct but slower C++ program -> correct and faster C++ program
```

A faster wrong program is a failure. The reward must first prove behavior is
preserved, then measure speed.

## Names Used Here

- `w8-biayn`: this repository's CLI, usually run as `uv run w8-biayn ...`.
- PIE: the slower-to-faster C++ source dataset.
- SLIME: the active RL framework for SFT/GRPO experiments in this repo.
- Megatron: the training backend used by the SLIME lanes.
- SGLang: the rollout/inference backend used by the SLIME lanes.
- Moonlight: the active Moonlight-16B-A3B model lane.
- GLM: the active GLM-4.7-Flash model lane.
- Polyglot: optional Aider Polyglot C++ base-eval benchmark, separate from the PIE training proof.
- Multi-SWE: optional C++ issue-resolution base-eval benchmark, separate from the PIE training proof.
- Docker sandbox: the compile/test/runtime harness for C++ reward execution.

SkyRL/rLLM names may still appear in legacy files. Treat that stack as retired
for active training unless a task explicitly asks for compatibility work.

## Core Learning Problem

The model is not trained to solve arbitrary programming tasks from scratch. It
receives a complete C++ program that already solves the problem and must return
a complete C++ program that still solves the problem faster.

That shape changes the work:

- data must preserve slower/faster program pairs;
- prompts must show `v0` and may show visible tests;
- GRPO prompts must not show `v1` or hidden tests;
- reward must compile, sanitize, test, and benchmark generated code.

## What One Task Contains

Each admitted PIE task contains:

- `v0`: slower accepted C++ program, visible in the prompt;
- `v1`: faster accepted C++ program, used for SFT/reference only;
- visible tests: prompt-visible behavior examples;
- hidden tests: grading-only behavior checks;
- reference performance: timing material for speed comparison;
- split: train, validation, or test, split by problem.

The prompt may include `v0` and visible tests. It must not include `v1` or
hidden tests during GRPO.

## Why SFT Still Matters

SFT uses PIE `v0 -> v1` pairs:

```text
prompt: instruction + slower C++ v0
target: <reasoning>...</reasoning> + faster C++ v1 in one fenced cpp block
```

SFT teaches output format, complete compilable C++, and common optimization
patterns. It does not prove held-out optimization. GRPO is still needed to
learn from correctness-gated runtime reward.

## Required Output Format

Every model output must contain exactly one reasoning block followed by exactly
one fenced C++ block:

````text
<reasoning>
Brief optimization rationale.
</reasoning>
```cpp
// complete C++20 program
```
````

The parser may tolerate recoverable bare C++ for shaped reward, but strict
format remains the training target.

## Reward Ladder

Reward should enforce this order:

1. Invalid format is negative.
2. Compile or sanitizer failure is negative.
3. Timeout is negative.
4. Partial test pass remains below any fully correct answer.
5. All visible and hidden tests passing earns positive correctness reward.
6. Fully correct with missing non-timeout runtime gets a correctness-only
   fallback below measured correct outputs.
7. Fully correct and faster earns bounded runtime-efficiency bonus.

The active speed signal is child-process CPU time in nanoseconds. Wall-clock
time is diagnostic. Do not add PMU, Linux perf, PERFMON, or
`perf_event_paranoid` requirements.

## Agentic File-State Variant

GLM-4.7-Flash is a thinking model whose `<think>` block overruns a single-turn
response budget, truncating answers so they cannot be parsed or scored. The
`examples/slime/glm47_swe_agent_cpp_perf/` lane fixes this by scoring the FILE,
not model text: SWE-agent (not claude-code) edits `candidate.cpp` over many
turns and the final file is graded with the same reward ladder above
(compile/tests/child-CPU-ns) in the repo's Docker sandbox (not E2B). Reward
flows via the SLIME OpenAI adapter `finish_session`, so the single-turn
"Required Output Format" does not apply to this lane. SFT stays single-turn as a
C++-quality warm-start; base/sft/grpo evals and GRPO are agentic. SWE-agent runs
its edit/bash loop in-process on the rollout worker via swerex `LocalDeployment`
(no sibling container, no `--network host` — which collided with Ray); only the
final-file grading re-enters the Docker sandbox. See `slime_swe_agent_cpp_perf.py`
and `swe_agent_driver.py`.

Status: **proven end-to-end.** Run `w8swe-20260707091714` completed all seven
stages in 78 minutes on spot A100s — including a clean GRPO weight update
(`train/ppo_kl` finite, `zero_variance_group_fraction` 0,
`trained_tokens_mean` 161, 87.5% eval pass at every stage) — with checkpoints
and HF exports fully persisted to GCS. The eight-smoke campaign's fixes are
each pinned by a regression lint (`tests/test_regression_lints.py`): swerex
shared-filesystem collisions, weight-shard export gates + readable/loud/
retried persist, `round_number` on every trainer sample, one trainable sample
per episode (GRPO group shape), pin-local upstream fetches, network
preflight + watchdog, and `CLUSTER_LOST` spot-preemption auto-retry. W&B is
the verification instrument throughout (README Observability section,
`w8-biayn wandb workspace`). Open before the full run: episode forks still
occur at 3/episode (the keep-best guard preserves group math but discards
~2/3 of captured tokens — investigate adapter REALIGN vs GLM think-stripping)
plus the pre-existing gates (thinking budget, PIE admission coverage,
model/torch_dist GCS cache).

## Stage 0: Prove The Local Runtime

Question:

> Can the machine prepare data, run SLIME, and execute the C++ harness?

Commands:

```bash
./scripts/bootstrap.sh
uv run w8-biayn data doctor
uv run w8-biayn upstreams clone slime
uv run w8-biayn slime doctor
uv run w8-biayn slime setup
uv run w8-biayn cpp harness preflight --dry-run
```

Decision gate: do not start paid or long GPU work until SLIME setup and C++
harness preflight are clean. Use the generated `.w8-biayn/slime/run-container.sh`
for SLIME entry; it owns the host-visible short temp mount needed by nested
Docker rewards and Ray.

## Stage 1: Build Admitted PIE Tasks

Question:

> Do we have tasks strong enough to teach and grade optimization?

Commands:

```bash
uv run w8-biayn data pie download --out .w8-biayn/data/pie
uv run w8-biayn data pie prepare-full \
  --source-root .w8-biayn/data/pie \
  --out .w8-biayn/data/pie-full \
  --force

uv run w8-biayn data pie measure-coverage \
  --prepared-root .w8-biayn/data/pie-full \
  --out .w8-biayn/data/pie-full/coverage.json \
  --report-out .w8-biayn/data/pie-full/coverage-report.json

uv run w8-biayn data pie build-full-tasks \
  --prepared-root .w8-biayn/data/pie-full \
  --coverage-json .w8-biayn/data/pie-full/coverage.json \
  --out .w8-biayn/data/tasks-full \
  --min-train 1000 \
  --min-validation 100 \
  --min-test 100 \
  --force
```

Admission gates:

- train tasks >= 1000;
- validation/test tasks >= 100;
- line coverage >= 95 percent;
- branch coverage >= 85 percent;
- visible and hidden tests exist;
- reference performance exists.

## Stage 2: Build SLIME JSONL

Question:

> Can admitted C++ tasks become SLIME SFT, GRPO, and eval rows?

Moonlight lane:

```bash
bash examples/slime/moonlight_cpp_perf/prepare_data.sh
```

Moonlight rank-16 LoRA lane:

```bash
bash examples/slime/moonlight_lora_cpp_perf/prepare_data.sh
```

GLM lane when present:

```bash
bash examples/slime/glm47_cpp_perf/prepare_data.sh
```

The underlying bridge is `w8_biayn.integrations.slime_cpp_perf`. It writes
SLIME JSONL and task copies while reusing the same prompt and reward contract.

Decision gate: inspect the generated manifest and sample rows before training.

## Stage 3: Baseline The Base Model

Question:

> What can the base Moonlight or GLM checkpoint already do?

Moonlight:

```bash
bash examples/slime/moonlight_cpp_perf/eval_base.sh
```

GLM:

```bash
bash examples/slime/glm47_cpp_perf/eval_base.sh
```

Inspect invalid-format rate, compile failures, hidden-test pass rate,
correct-and-faster rate, and missing runtime rows.

Decision gate: do not claim training progress until baseline evaluation has
complete records and no unexplained missing runtime rows.



## Optional Side Benchmark: Polyglot C++ Base Eval

Question:

> How does the base Moonlight checkpoint perform on Aider Polyglot C++
> exercises under a repo-owned SLIME rollout-only harness?

This benchmark is separate from the active PIE optimization training proof. It
uses whole-file solution replacement prompts and Exercism C++ tests, not PIE
`v0 -> v1` speed reward and not the official Aider edit harness. The canonical
operator flow is `examples/slime/moonlight_polyglot_cpp/README.md`; this
roadmap keeps only the decision point.

Decision gate: schema-v2 preparation must materialize the upstream
`files.example` references and pass every selected exercise through the same
Docker grader. Records are flushed per task and fingerprint the exact copied
task, mapping, grader configuration, and immutable image ID. `verify-data`
must recompute the summary and reconcile records, eval rows, current files,
mappings, and manifest counts before admission. Inspect `data/oracle.records.jsonl`,
`data/oracle.summary.json`, `eval/base.records.jsonl`,
`eval/base.summary.json`, and `stages/base-eval/run_receipt.txt`. Require
`base.summary.json.oracle_setup_check.schema_version == 2`,
`oracle_protocol_version == 1`, `complete`, and `all_passed` before treating
model failures as setup-clean. Keep Polyglot C++ results separate from both PIE
uplift claims and Aider leaderboard numbers.
The one-shot launcher must enable SLIME's supported special-token skipping so
terminal tokenizer markers are removed during decoding; parser strictness
against real prose outside the required path/code blocks remains unchanged.

For completed pass@1/pass@8 runs, the `compare-runs` report is the presentation
gate: derive a uniform `k` from records, require successful and comparable
receipts, recompute summaries, and match task plus oracle fingerprints before
charting. Use the six mutually-exclusive report categories for grouped pass@k
bars and sample-outcome stacked bars while retaining the source summary's
fine-grained multi-label taxonomy. Include the admitted `files.example` oracle
as a 100%-passing same-grader setup ceiling in overall and category views, and
label it as reference setup rather than a model or official Aider result. Keep
task-level empirical pass@k distinct from model-sample outcome distributions
and from the oracle's blocking setup outcomes.

Intentional temperature/top-p differences require the explicit
`--allow-config-mismatch` field override. Such output must record per-run
sampling, carry descriptive labels and a prominent confounding warning, and
must not be interpreted as the isolated effect of changing `k`.

Optional cross-model gate: `gemini-sanity` may run exactly one admitted prompt
through an exact Gemini model id, then the same strict parser and Docker grader.
It must dry-run before the paid API call, keep the API key in environment only,
persist prompt/raw-response/request/record/summary artifacts, expose no oracle
or test content, perform no response repair, and report recovered fields as
diagnostic only. It must also preflight artifact-path permissions before the
paid request. This is a prompt/parser/grader sanity check, not pass@k or an
official Polyglot/Aider comparison.

## Optional Side Benchmark: Official Aider C++ On Modal

Question:

> How does the base `zai-org/GLM-4.7-Flash` checkpoint perform on the C++
> subset of Aider Polyglot through Aider's own benchmark harness when both
> serving and benchmark execution run on Modal?

This result family is separate from PIE training and from the repo-owned
Moonlight Polyglot prompt/parser/grader. It uses Aider's edit application,
sequential test-feedback retries, C++ command, and authoritative statistics.
`pass_rate_2` is cumulative success after the second try, not pass@2. The
canonical export-only flow is
`examples/modal/glm47_flash_aider_polyglot_cpp/README.md`; the only entrypoint
is that directory's `run.sh`.

Decision gate: plan must be redacted and no-spend by default. A paid full run
requires exact model/Aider/Polyglot/SGLang identities, strict `H100!:4`, one
authenticated SGLang replica with reasoning separation, and a blocking
two-task Aider smoke. Admit the result only when all 26 official per-task
result/history files exist, Aider stats report 26 cases, the local copy matches
the committed results Volume, and control-plane verification proves the
ephemeral App stopped. Keep source/offline-test completion distinct from live
evidence: the implementation exists, but real CPU/Volume, real-weight server,
two-task smoke, and full-run receipts remain pending.
Permit up to 3600 seconds for a cold SGLang load, but poll the child process so
an early exit fails immediately. On failure, require a committed
bearer-redacted `server.failure.json` tail while raw SGLang output remains
ephemeral.
The digest-pinned SGLang image must overlay Transformers commit
`76732b4e7120808ff989edbd16401f61fa6a0afa`, fail its image build unless
`glm4_moe_lite` is registered, and record the commit in plans and receipts
before GPU admission.
Reject stale remote run artifacts in a CPU-only preflight before model loading
or GPU admission. After that gate, permit an SGLang container restart only
when the runner-written config is identity-compatible; it must not mistake its
own active run artifacts for operator reuse.
Give the authenticated chat admission probe up to 2048 tokens, bounded by the
configured benchmark maximum, because a thinking response can exhaust 128
tokens before emitting editable content. Persist `admission.response.json` on
success or `admission.failure.json` on failure with response-shape metadata
only; never persist generated reasoning or answer text in these diagnostics.
Keep the pinned Aider checkout at `/aider`: its official C++ dispatcher uses
the absolute `/aider/benchmark/cpp-test.sh` path. Fail runner image construction
unless that script is executable and the pinned dispatcher still references
it. For any exception-only rows, persist and print a bearer-redacted
task/type/final-line summary before failing admission.
Use a 32768-token Aider completion budget. A paid smoke proved that 8192 can be
consumed entirely by GLM reasoning; the larger bound remains inside the exact
checkpoint's 202752-position context. On admission failure, print only safe
per-task counters and download the committed failure subtree locally before
re-raising the remote error.
Do not use pinned Modal SDK 1.5.2's `App.server` for the long-lived SGLang
replica: its hidden service Function retains the SDK's 300-second execution
timeout and causes five-minute container recycling. Use the public
`@app.function` plus `@modal.web_server` path with an explicit lifetime of
cold-start timeout plus runner timeout plus 600 seconds. Record that derived
timeout in plans and receipts. Keep static `min_containers=0`, then dynamically
hold exactly one replica (`min_containers=1`) only after CPU/Volume admission
and model-cache preparation. Keep that lease through all Aider work. On either
success or error, restore `min_containers=0` and a two-second drain before
artifact transfer; explicit stop and control-plane verification still close
the App. The 1200-second window remains an identity-bound fallback. The
execution lifetime and active lease are operational rather than benchmark
identity, so old compatible artifacts may resume with them enabled.
When downloading recursive Volume artifacts under Modal SDK 1.5.2, read only
entries whose public type is exactly `FileEntryType.FILE`. Skip directories,
symlinks, and other non-regular entries before `read_file`, then preserve the
existing byte-for-byte local reconciliation. Validate all paths before local
writes, use the SDK async API with a fixed 16-file concurrency bound, and emit
progress. Once the remote result is committed, reduce the server scaledown
window to two seconds before downloading so artifact transfer does not retain
the four-H100 replica.

The updated independent result-family design uses eight trajectories per task,
each with up to two sequential Aider tries. It reports exactly
`pass@1_try1`, `pass@1_try2`, `pass@8_try1`, and `pass@8_try2` from separate
try-1 and cumulative-try-2 matrices. State and feedback may continue from try
1 to try 2 only within one trajectory; all eight trajectories remain isolated.
Source and offline regressions implement the two-try/four-metric protocol.
Seed inspection, the 2-by-8-by-try smoke, a complete 26-by-8-by-try run, and
stopped-App proof remain blocking before reporting live metrics. Offline
visualization runs through `python -m w8_biayn.modal_aider_visualization`,
keeps reports under `reports/<run-id>/`, and labels prefix-only evidence as
partial diagnostics rather than final pass@8. It also assigns all 26 tasks to
six stable, mutually-exclusive topic groups of 3-6 tasks and to a balanced
8/9/9 Easy/Medium/Hard task-complexity taxonomy, with grouped initial and
cumulative-try-2 summaries. These labels stay fixed across runs; observed
success counts remain a separate empirical difficulty signal.
Treat both paid acknowledgements as launch safety gates, not immutable result
identity: a reviewed no-spend plan may enable them for the first paid invocation
without becoming a resume/config mismatch.
The eight sampling-smoke trajectories must all use the fixed
`binary-search-tree,grade-school` Aider keyword filter and the versioned
`sampling-smoke-v1` artifact path; randomized legacy subsets never count.
Independent full runs require the 14,400-second bound observed necessary after a
roughly 70-minute sampling smoke; do not resume a 7,200-second identity with a
changed timeout.
Treat Aider's misleading `num_exhausted_context_windows` counter as an
output-limit model diagnostic: a length-finished response can still apply an
edit and pass tests. It must not independently turn complete non-exception rows
with C++ test invocations into an infrastructure failure.
Commit an App-bound `runner.identity.json` before Aider work so Modal worker
re-entry accepts only the same App and immutable config. Explicit independent
resume reuses only fully validated sample rows plus stats, preserves an
interrupted sample under `incomplete-attempts/`, and restarts that sample from
the pinned tree with its original seed. Archive the previous local failure
download before exact resumed transfer. Enabling the active-server lease is
compatible with pre-lease artifacts.

## Optional Side Benchmark: Multi-SWE C++ Base Eval

Question:

> How does the base Moonlight checkpoint perform on Multi-SWE-bench mini C++
> issue-resolution instances under a repo-owned SLIME rollout-only harness?

This benchmark is separate from the active PIE optimization training proof. It
uses single unified-diff patch prompts, dataset `test_patch` application,
forbidden-path preflight, and repository-specific C++ tests, not PIE `v0 -> v1`
speed reward and not the official Multi-SWE evaluator. The canonical operator
flow is `examples/slime/moonlight_multi_swe_cpp/README.md`; this roadmap keeps
only the decision point.

Decision gate: before model loading, require schema-v3 `data/manifest.json`
to say `admitted: true`, `data/oracle.summary.json.all_passed` and
`complete` to be true, every oracle record to report a positive CTest count,
and `data/sandbox-images.json` to prove official per-task immutable images.
The standard grader must use the image-prepared checkout/build/test assets
without per-task GitHub clones; preflight persists after every task and resumes
only fingerprint-matching passes. The four affected historical simdjson tasks
must also have a current `data/offline-dependencies.json` receipt for the
checksum-pinned `cxxopts`/simdjson-data cache mounted read-only into their
network-disabled graders. PR 958 additionally requires its narrow GCC 7 external-cxxopts
`-Wno-error=effc++` compatibility flag after target-level `-Werror`, an
external-header wrapper that keeps the full `-Weffc++` group visible but
non-fatal, and removal of only the network-dependent checkperf include; do not disable warnings-as-errors or the
ordinary benchmark/test build globally. Nlohmann PR 2099 must run its 49-test
dataset pass set and then explicitly run the PR-relevant `CBOR` and
`MessagePack` doctest cases, while excluding only their unrelated historical
roundtrip fixture cases. Then
inspect `eval/base.records.jsonl`, `eval/base.oracle.records.jsonl`,
`eval/base.summary.json`, and `stages/base-eval/run_receipt.txt`. Require the
copied `base.summary.json.oracle_setup_check.all_passed` before treating model
failures as setup-clean. Keep Multi-SWE C++ results separate from PIE uplift
claims, Polyglot C++ results, and official Multi-SWE leaderboard numbers.
The one-shot launcher must enable SLIME's supported special-token skipping so
terminal tokenizer markers are removed during decoding; parser strictness
against real prose outside the single diff fence remains unchanged.

## Stage 4: Run SFT

Question:

> Can supervised learning improve format, compilability, and basic rewrite
> quality?

Moonlight:

```bash
bash examples/slime/moonlight_cpp_perf/sft.sh
bash examples/slime/moonlight_cpp_perf/eval_sft.sh
```

GLM:

```bash
bash examples/slime/glm47_cpp_perf/sft.sh
bash examples/slime/glm47_cpp_perf/eval_sft.sh
```

Expected improvements:

- higher strict-format rate;
- fewer compile failures;
- more fully correct outputs;
- more useful starting point for GRPO.

Decision gate: verify the SFT checkpoint/export used for GRPO is complete and
loadable by the lane's SGLang path. The LoRA lane checks the active
SLIME/Megatron help surface before SFT/GRPO so rank-16 LoRA arguments cannot be
silently ignored.

Optional Moonlight format-discipline smoke:

```bash
uv run python -m w8_biayn.integrations.moonlight_single_sample_sft \
  --out .w8-biayn/data/aider-whole-single
```

Then, inside the SLIME container, run the existing non-LoRA SFT wrapper with:

```bash
export SLIME_RUN_ID=moonlight-aider-whole-single-sft
export SLIME_CPP_DATA_DIR="$PWD/.w8-biayn/data/aider-whole-single"
export SLIME_CPP_AUTO_PREPARE_DATA=0
export SLIME_SFT_ROLLOUT_BATCH_SIZE=1
export SLIME_SFT_GLOBAL_BATCH_SIZE=1
export SLIME_SFT_NUM_EPOCH=1
export SLIME_SAVE_INTERVAL=1
bash examples/slime/moonlight_cpp_perf/sft.sh
```

This single-sample Aider `whole` edit-format SFT smoke does not run
`prepare_data.sh`, PIE eval, GRPO, GLM, or LoRA, and it must not be reported as
uplift or benchmark evidence.

## Stage 5: Run GRPO From SFT

Question:

> Can reward optimization beat base and SFT on correctness-gated speed?

Moonlight:

```bash
bash examples/slime/moonlight_cpp_perf/grpo.sh
bash examples/slime/moonlight_cpp_perf/eval_grpo.sh
bash examples/slime/moonlight_cpp_perf/compare.sh
```

Moonlight rank-16 LoRA variant:

```bash
bash examples/slime/moonlight_lora_cpp_perf/grpo.sh
bash examples/slime/moonlight_lora_cpp_perf/eval_grpo.sh
bash examples/slime/moonlight_lora_cpp_perf/compare.sh
```

GLM:

```bash
bash examples/slime/glm47_cpp_perf/grpo.sh
bash examples/slime/glm47_cpp_perf/eval_grpo.sh
bash examples/slime/glm47_cpp_perf/compare.sh
```

Watch for:

- reward rising while held-out eval stalls;
- response-length drift;
- invalid-format regressions;
- hidden-test regressions;
- C++ reward workers bottlenecking GPU training;
- SGLang startup or memory failures.

Decision gate: a useful result beats base and SFT on held-out
`correct_and_faster_rate` and mean best reward with missing-runtime rate at
zero. For the paid GCP GLM path,
`examples/slime/glm47_cpp_perf/launch_gcp_h100_full.py` provisions one
`H100:8` SkyPilot cluster, runs the full GLM sequence, downloads artifacts to
`.w8-biayn/slime/glm47-cpp-perf/`, and calls `sky.down` after completion.

## Stage 6: Compare Moonlight And GLM

Question:

> Which active model lane is the better next investment?

Compare the lane-local `comparison.json` files and run receipts:

- base/SFT/GRPO pass rate;
- correct-and-faster rate;
- mean best reward;
- runtime speedup among correct faster outputs;
- missing-runtime rows;
- GPU memory peak;
- rollout/training wall time;
- reward throughput.

Do not answer "is GLM faster?" or "is Moonlight better?" from model size or GPU
count alone. Use comparable runs on the same task split and reward harness.

## Stage 7: Archive Evidence Without Tracking Artifacts

Run receipts, debug rollouts, checkpoint exports, W&B links, raw reports, SVGs,
and CSVs are evidence artifacts. Keep them under `.w8-biayn/` or another
ignored artifact directory. Do not commit generated `RUN_REPORT*` files or
report asset directories.

When a result is worth preserving in git, write a concise markdown summary that
links to durable external artifacts without vendoring large/generated files.


## Optional Side Benchmark: GLM Multi-SWE C++ On Modal

Question:

> How does base GLM-4.7-Flash perform on the 50 C++ Multi-SWE-bench mini
> instances under the repository's single-turn diff contract when serving and
> isolated grading run on Modal?

The canonical export-only flow is
examples/modal/glm47_flash_multi_swe_cpp/README.md. Plan is no-spend by
default. Smoke/full require the checked-in exact dataset revision and 50-image
linux/amd64 digest lock, an all-task fix_patch proof for the same
network-blocked Modal Sandbox backend, one strict H100!:4 SGLang replica,
separated reasoning/content, and the fixed two-task smoke. A fresh full run may
import that proof from an explicitly named completed run only when its stopped
receipt and artifact manifest reconcile and all 50 current oracle cache keys
match; requested import never falls back to executing oracles.

Decision gate: source and offline contracts are implemented and the paid
two-task smoke is infrastructure-clean, but full validation is pending. Do not
publish a result until all 50 saved responses
map to 50 complete records, the strict summary recomputes with a passing oracle
proof, artifacts reconcile byte-for-byte, every Sandbox terminated/detached,
and the App receipt says modal_app_stopped: true. Label the result repo-owned,
correctness-only, and modal-sandbox; never call it an official leaderboard
score or report PIE speed metrics. Stage the two simdjson dependency trees
beneath one checksum-pinned read-only parent mounted at a fresh /mnt path;
Modal SDK 1.5.2 forbids both mounting the same Volume at two Sandbox paths and
mounting over the official image's non-empty dependency directory. After patch
preflight, the trusted grader links only the two expected dependency subtrees
into the checkout before tests. An interrupted oracle-only run may migrate
source commit/file hashes for an infrastructure fix and reuse only records
with exact oracle cache keys. Any persisted model-cache, SGLang, admission,
smoke, full, or final artifact makes source identity strict again. Parse CTest
discovery from complete in-memory stdout/stderr before truncation, persist the
numeric count plus per-stream hashes/sizes, and retain bounded tails from both
streams; compiler-warning volume must never erase positive test evidence.
Keep min_containers=0 but poll the externally routed health endpoint through
Modal's zero-to-one HTTP 503 window before models/chat admission. Persist only
status/count/body-size/hash/JSON-key diagnostics, never HTTP body text. Permit
source-only repair through preparation and admission failures—including an
exact model-cache receipt—but block it after successful admission or any
smoke/full/final artifact.
Keep the dataset image lock control-plane-only: do not attach it to the GPU
server image. Server module hydration must tolerate its absence, while local
orchestration must require the reviewed lock before preflight or paid work.
Persist imported proof lineage in the new run and never import the source
smoke's model responses or mutate the completed source run.

## Optional Side Benchmark: Agentic GLM Multi-SWE C++ On Modal

Question:

> How does exact-revision base GLM-4.7-Flash perform on the locked 50 C++
> Multi-SWE mini tasks when one bounded SWE-agent trajectory may inspect and
> edit sanitized source, while the unchanged fresh Modal grader judges a
> trusted file-state diff?

The separately named source lane and offline contracts are implemented under
examples/modal/glm47_flash_agentic_multi_swe_cpp/. Phase one remains exactly
one deterministic trajectory per task. Safe step/tool receipts are incremental,
and full repeats the fixed smoke with a release/re-admission boundary before its
50-task stage. It is not SLIME, PIE training, Aider, pass@8, or an official
leaderboard result.

Agentic run IDs are limited to 3-40 lowercase letters, digits, or hyphens. This
admits the documented timestamped plan/smoke/full names while keeping the
derived Modal App name at most 62 characters.

Decision gate: plan, config, exact SWE-agent/dependency identity, sanitizer and
finalizer, Modal adapter, all-50 oracle/workspace admission, trajectory resume,
release-before-grading orchestration, artifact validation, wrapper, tests, and
runbook are complete. Paid CPU canaries, real SGLang admission, one trajectory,
the fixed two-task smoke, and the stopped-App full receipt remain pending. Full
must not launch before a clean smoke.

All model-controlled commands stay in unprivileged, network-blocked,
secret-free, Volume-free Agent Sandboxes. Trusted code removes hidden assets
and original history, owns the baseline, rejects unsafe final trees, and
synthesizes a patch that must apply to a pristine reconstruction. Exact empty
directories for uninitialized gitlinks remain present and receipt-bound;
populated submodules must match their indexed commits. The
workspace compile/output canary uses the exact image's default C++ mode for
legacy-image compatibility and does not alter task grader commands. The server
holds one H100!:4 replica only while trajectories run, then releases it before
separate fresh-Sandbox grading.

Never publish a score until all 50 trajectory, patch, and record units are
complete; all 50 exact oracle and workspace proofs pass; summaries recompute;
local and remote artifacts reconcile byte-for-byte; and the control plane
proves the App stopped. The canonical paid ladder and exports live only in the
lane README.
